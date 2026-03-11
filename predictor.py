import numpy as np
import pandas as pd
import sys
import os
import joblib
from math import exp, factorial
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from player_rater import PlayerRater

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("XGBoost not found, using MLP only.")
    sys.stdout.flush()

MODEL_DIR = os.path.dirname(__file__)
MLP_PATH = os.path.join(MODEL_DIR, "model_mlp.pkl")
XGB_PATH = os.path.join(MODEL_DIR, "model_xgb.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")


class Predictor:
    """
    Hybrid prediction engine:
    1. Poisson xG Model (statistical baseline)
    2. XGBoost + MLP Ensemble (machine learning)
    3. Injury adjustments (Transfermarkt)
    4. H2H adjustments (football-data.co.uk)

    Trained on real club data from football-data.co.uk (5 leagues × 4 seasons).
    """

    # Feature names (9 features) — must be consistent between training and inference
    FEATURE_NAMES = [
        'home_goals_avg', 'home_conceded_avg',
        'away_goals_avg', 'away_conceded_avg',
        'goal_diff',
        'home_form', 'away_form',
        'home_momentum', 'away_momentum'
    ]

    def __init__(self, data_fetcher):
        self.data_fetcher = data_fetcher
        self.player_rater = PlayerRater()
        self.model_mlp, self.model_xgb, self.scaler = self._load_or_train_models()

    def _load_or_train_models(self):
        """Load cached models or train from scratch using real club data."""
        if os.path.exists(MLP_PATH) and os.path.exists(SCALER_PATH):
            print("Kayıtlı modeller yükleniyor...")
            sys.stdout.flush()
            mlp = joblib.load(MLP_PATH)
            scaler = joblib.load(SCALER_PATH)
            xgb = joblib.load(XGB_PATH) if os.path.exists(XGB_PATH) and HAS_XGB else None
            print("Modeller başarıyla yüklendi!")
            sys.stdout.flush()
            return mlp, xgb, scaler

        return self._train_models()

    def _train_models(self):
        """Train MLP + XGBoost on real club data from football-data.co.uk."""
        print("=" * 60)
        sys.stdout.flush()
        print("Yapay Zeka modelleri gerçek kulüp verileriyle eğitiliyor...")
        sys.stdout.flush()
        print("=" * 60)
        sys.stdout.flush()

        X_raw, y_raw = self.data_fetcher.get_training_data()

        if len(X_raw) < 500:
            print(f"  UYARI: Yetersiz veri ({len(X_raw)}), sentetik veri ekleniyor...")
            sys.stdout.flush()
            X_raw, y_raw = self._add_synthetic_data(X_raw, y_raw)

        X = np.array(X_raw)
        y = np.array(y_raw)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # --- MLP ---
        print(f"  MLP eğitiliyor ({len(X)} örnek, {X.shape[1]} özellik)...")
        sys.stdout.flush()
        mlp = MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            max_iter=500,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1
        )
        mlp.fit(X_scaled, y)

        # --- XGBoost ---
        xgb = None
        if HAS_XGB:
            print(f"  XGBoost eğitiliyor...")
            sys.stdout.flush()
            xgb = XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                eval_metric='mlogloss',
                use_label_encoder=False
            )
            xgb.fit(X_scaled, y)

        # Save
        joblib.dump(mlp, MLP_PATH)
        joblib.dump(scaler, SCALER_PATH)
        if xgb:
            joblib.dump(xgb, XGB_PATH)

        print(f"  ✓ Modeller kaydedildi ({len(X)} maç ile eğitildi)")
        sys.stdout.flush()
        return mlp, xgb, scaler

    def _add_synthetic_data(self, X, y):
        """Emergency fallback: add synthetic data if real data is insufficient."""
        np.random.seed(42)
        n = 5000
        h = np.random.uniform(0.5, 3.0, n)
        hc = np.random.uniform(0.5, 2.5, n)
        a = np.random.uniform(0.3, 2.5, n)
        ac = np.random.uniform(0.5, 3.0, n)
        hf = np.random.uniform(0.2, 1.0, n)
        af = np.random.uniform(0.2, 1.0, n)
        hm = np.random.choice([-0.2, 0, 0.2], n)
        am = np.random.choice([-0.2, 0, 0.2], n)

        for i in range(n):
            hg = np.random.poisson(h[i] * (0.85 + hf[i] * 0.3))
            ag = np.random.poisson(a[i] * (0.85 + af[i] * 0.3))
            label = 1 if hg > ag else (0 if hg == ag else 2)
            X.append([h[i], hc[i], a[i], ac[i], h[i] - a[i], hf[i], af[i], hm[i], am[i]])
            y.append(label)

        return X, y

    # ═══════════════════════════════════════════════
    # Poisson xG Model
    # ═══════════════════════════════════════════════

    @staticmethod
    def _poisson_pmf(lam, k):
        """P(X=k) for Poisson distribution."""
        return (lam ** k) * exp(-lam) / factorial(k)

    def _poisson_match_probs(self, home_xg, away_xg, max_goals=8):
        """
        Compute 1/X/2 probabilities from Poisson distribution.
        P(home=i, away=j) = P_poisson(home_xg, i) × P_poisson(away_xg, j)
        """
        p_home, p_draw, p_away = 0.0, 0.0, 0.0

        for i in range(max_goals):
            for j in range(max_goals):
                p = self._poisson_pmf(home_xg, i) * self._poisson_pmf(away_xg, j)
                if i > j:
                    p_home += p
                elif i == j:
                    p_draw += p
                else:
                    p_away += p

        total = p_home + p_draw + p_away
        if total > 0:
            p_home /= total
            p_draw /= total
            p_away /= total

        return p_home, p_draw, p_away

    def _compute_xg(self, home_stats, away_stats):
        """
        Compute expected goals using attack/defense strengths relative to league average.
        Standard Dixon-Coles approach.
        """
        lg_home = home_stats.get('league_avg_home_goals', 1.5)
        lg_away = home_stats.get('league_avg_away_goals', 1.15)

        # Attack strength = team's scoring / league average
        # Defense strength = team's conceding / league average
        home_attack = home_stats['home_goals_scored'] / max(lg_home, 0.5)
        home_defense = home_stats['home_goals_conceded'] / max(lg_away, 0.5)
        away_attack = away_stats['away_goals_scored'] / max(lg_away, 0.5)
        away_defense = away_stats['away_goals_conceded'] / max(lg_home, 0.5)

        home_xg = home_attack * away_defense * lg_home
        away_xg = away_attack * home_defense * lg_away

        # Clamp to reasonable range
        home_xg = max(0.3, min(4.5, home_xg))
        away_xg = max(0.3, min(4.5, away_xg))

        return round(home_xg, 2), round(away_xg, 2)

    # ═══════════════════════════════════════════════
    # ML Ensemble Prediction
    # ═══════════════════════════════════════════════

    def _ml_predict(self, home_stats, away_stats):
        """Get ML ensemble probabilities from XGBoost + MLP."""
        features = np.array([[
            home_stats['home_goals_scored'],
            home_stats['home_goals_conceded'],
            away_stats['away_goals_scored'],
            away_stats['away_goals_conceded'],
            home_stats['home_goals_scored'] - away_stats['away_goals_scored'],
            home_stats['form'],
            away_stats['form'],
            home_stats['momentum'],
            away_stats['momentum'],
        ]])

        X_scaled = self.scaler.transform(features)

        # MLP probabilities
        mlp_probs = self.model_mlp.predict_proba(X_scaled)[0]
        # Classes should be [0, 1, 2] = [Draw, Home, Away]
        classes = list(self.model_mlp.classes_)

        p_home_mlp = mlp_probs[classes.index(1)] if 1 in classes else 0.33
        p_draw_mlp = mlp_probs[classes.index(0)] if 0 in classes else 0.33
        p_away_mlp = mlp_probs[classes.index(2)] if 2 in classes else 0.33

        if self.model_xgb is not None:
            xgb_probs = self.model_xgb.predict_proba(X_scaled)[0]
            xgb_classes = list(self.model_xgb.classes_)
            p_home_xgb = xgb_probs[xgb_classes.index(1)] if 1 in xgb_classes else 0.33
            p_draw_xgb = xgb_probs[xgb_classes.index(0)] if 0 in xgb_classes else 0.33
            p_away_xgb = xgb_probs[xgb_classes.index(2)] if 2 in xgb_classes else 0.33

            # Weighted ensemble: 60% XGBoost + 40% MLP
            p_home_ml = 0.6 * p_home_xgb + 0.4 * p_home_mlp
            p_draw_ml = 0.6 * p_draw_xgb + 0.4 * p_draw_mlp
            p_away_ml = 0.6 * p_away_xgb + 0.4 * p_away_mlp
        else:
            p_home_ml = p_home_mlp
            p_draw_ml = p_draw_mlp
            p_away_ml = p_away_mlp

        return p_home_ml, p_draw_ml, p_away_ml

    # ═══════════════════════════════════════════════
    # Main Probability Calculation
    # ═══════════════════════════════════════════════

    def calculate_probabilities(self, home_team, away_team):
        """
        Hybrid prediction combining:
        1. Poisson xG model (30% weight) - statistical baseline
        2. ML Ensemble (40% weight) - XGBoost/MLP trained on real data
        3. Elo-based (30% weight) - calibrated win expectancy
        4. H2H adjustment (±3%)
        5. Injury adjustment (up to -20%)
        """
        home_stats = self.data_fetcher.get_team_stats(home_team)
        away_stats = self.data_fetcher.get_team_stats(away_team)

        if not home_stats or not away_stats:
            return None

        # Elo ratings and Sources
        home_elo = home_stats.get('elo')
        away_elo = away_stats.get('elo')
        
        home_elo_src = home_stats.get('data_quality', {}).get('elo_source', 'Unknown')
        away_elo_src = away_stats.get('data_quality', {}).get('elo_source', 'Unknown')

        if home_elo is None or away_elo is None or home_elo_src != 'ClubElo' or away_elo_src != 'ClubElo':
            # Skip matches where we don't have real ClubElo data
            missing = []
            if home_elo is None or home_elo_src != 'ClubElo': missing.append(home_team)
            if away_elo is None or away_elo_src != 'ClubElo': missing.append(away_team)
            print(f"  [!] Genuine ClubElo Rating Not Found for: {', '.join(missing)} - Skipping match.")
            return {'Skip_Reason': f"Elo Not Found for {', '.join(missing)}"}

        elo_h, elo_a = float(home_elo), float(away_elo)

        # 1. Poisson xG
        home_xg, away_xg = self._compute_xg(home_stats, away_stats)
        p_home_poi, p_draw_poi, p_away_poi = self._poisson_match_probs(home_xg, away_xg)

        # 2. ML Ensemble
        p_home_ml, p_draw_ml, p_away_ml = self._ml_predict(home_stats, away_stats)

        # 3. Elo-based
        elo_diff = elo_h - elo_a + 30  # 30 pts home advantage
        p_home_elo = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
        # A simple empirical model for draw probability based on Elo difference
        abs_diff = abs(elo_h - elo_a)
        p_draw_elo = max(0.15, 0.25 - abs_diff / 1000.0)
        p_away_elo = 1.0 - p_home_elo - p_draw_elo
        if p_away_elo < 0: p_away_elo = 0

        # Normalizing Elo probabilities to sum to 1
        total_elo = p_home_elo + p_draw_elo + p_away_elo
        p_home_elo /= total_elo
        p_draw_elo /= total_elo
        p_away_elo /= total_elo

        # ── Blend: 30% Poisson + 40% ML + 30% Elo ──
        p_home = 0.30 * p_home_poi + 0.40 * p_home_ml + 0.30 * p_home_elo
        p_draw = 0.30 * p_draw_poi + 0.40 * p_draw_ml + 0.30 * p_draw_elo
        p_away = 0.30 * p_away_poi + 0.40 * p_away_ml + 0.30 * p_away_elo

        # ── 4. H2H adjustment ──
        h2h = self.data_fetcher.get_h2h(home_team, away_team)
        h2h_total = h2h.get('total', 0)
        if h2h_total >= 3:
            dominance = h2h.get('home_dominance', 0)
            h2h_shift = dominance * 0.03  # max ±3%
            p_home += h2h_shift
            p_away -= h2h_shift

        # ── 5. Injury adjustment ──
        home_injuries = self.data_fetcher.get_transfermarkt_injuries(home_team)
        away_injuries = self.data_fetcher.get_transfermarkt_injuries(away_team)

        # Baseline squad values for calculations (heuristic placeholders)
        h_squad_val = 150.0 if elo_h < 1800 else 400.0
        a_squad_val = 150.0 if elo_a < 1800 else 400.0

        home_penalty = 0.0
        home_injury_names = []
        for inj_dict in home_injuries:
            rd = self.player_rater.get_player_rating(inj_dict, home_team, h_squad_val)
            home_penalty += rd.get('impact_weight', 0.015)
            # Format: Name (Category/Value)
            home_injury_names.append(f"{inj_dict['name']} ({rd.get('impact_category', '?')})")

        away_penalty = 0.0
        away_injury_names = []
        for inj_dict in away_injuries:
            rd = self.player_rater.get_player_rating(inj_dict, away_team, a_squad_val)
            away_penalty += rd.get('impact_weight', 0.015)
            away_injury_names.append(f"{inj_dict['name']} ({rd.get('impact_category', '?')})")

        # Cap max penalty so it doesn't wreck the system completely (e.g. half squad missing)
        home_penalty = min(0.20, home_penalty)
        away_penalty = min(0.20, away_penalty)

        p_home = p_home * (1.0 - home_penalty) + p_away * away_penalty * 0.5
        p_away_adj = p_away * (1.0 - away_penalty) + p_home_elo * home_penalty * 0.5
        p_away = p_away_adj
        p_draw = 1.0 - p_home - p_away

        # Clamp & normalize
        p_home = max(0.02, min(0.95, p_home))
        p_away = max(0.02, min(0.95, p_away))
        p_draw = max(0.02, min(0.50, p_draw))
        t = p_home + p_draw + p_away
        p_home /= t
        p_draw /= t
        p_away /= t

        ret_dict = {
            '1': round(p_home, 3),
            'X': round(p_draw, 3),
            '2': round(p_away, 3),
            'Home_xG': home_xg,
            'Away_xG': away_xg,
            'Home_Elo': int(elo_h),
            'Away_Elo': int(elo_a),
            'Home_Form': round(home_stats.get('form', 0.5), 2),
            'Away_Form': round(away_stats.get('form', 0.5), 2),
            'Home_Mom': round(home_stats.get('momentum', 0.0), 2),
            'Away_Mom': round(away_stats.get('momentum', 0.0), 2),
            'Home_Penalty_Pct': round(home_penalty * 100, 1),
            'Away_Penalty_Pct': round(away_penalty * 100, 1),
            'Home_Missing_Strs': home_injury_names,
            'Away_Missing_Strs': away_injury_names,
            'H2H_Total': h2h_total,
            'H2H_Home_Wins': h2h.get('home_wins', 0),
            'H2H_Draws': h2h.get('draws', 0),
            'H2H_Away_Wins': h2h.get('away_wins', 0),
            'Poisson_Home': round(p_home_poi, 3),
            'Poisson_Draw': round(p_draw_poi, 3),
            'Poisson_Away': round(p_away_poi, 3),
            'AI_Type': 'Poisson xG + XGBoost/MLP Ensemble + Elo'
        }
        
        # ── Data Quality / Reliability ──
        h_dq = home_stats.get('data_quality', {})
        a_dq = away_stats.get('data_quality', {})
        
        flags = []
        is_low = False
        is_medium = False
        
        for dq in [h_dq, a_dq]:
            if dq.get('elo_source') != 'ClubElo':
                flags.append('Elo_Ikincil_veya_Tahmini')
                is_medium = True
            if dq.get('stats_source') != 'football-data':
                flags.append('Istatistik_Eksik_veya_Tahmini')
                is_low = True
            if dq.get('injury_source') != 'Transfermarkt':
                flags.append('Sakatlik_Ikincil_veya_Yok')
                is_medium = True
                
        # Remove duplicates
        flags = list(set(flags))
        
        if is_low:
            reliability = 'Low'
        elif is_medium:
            reliability = 'Medium'
        else:
            reliability = 'High'
            
        ret_dict['Reliability'] = reliability
        ret_dict['Reliability_Flags'] = flags

        return ret_dict


if __name__ == "__main__":
    from data_fetcher import HistoricalDataFetcher
    fetcher = HistoricalDataFetcher()
    predictor = Predictor(fetcher)
    probs = predictor.calculate_probabilities("Galatasaray", "Fenerbahce")
    print("Sonuçlar (Galatasaray vs Fenerbahce):", probs)
