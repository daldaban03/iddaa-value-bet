import numpy as np
import pandas as pd
import requests
import io
import os
import joblib
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from player_rater import PlayerRater

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
SCALER_PATH = os.path.join(os.path.dirname(__file__), "scaler.pkl")

class Predictor:
    def __init__(self, data_fetcher):
        self.data_fetcher = data_fetcher
        self.player_rater = PlayerRater()
        self.model, self.scaler = self._train_neural_network()

    def _train_neural_network(self):
        """
        Trains MLP Neural Network on REAL historical football data.
        
        Features (7 per match) — consistent between training and inference:
          1. home_avg_goals   — goals scored average (rolling 10)
          2. away_avg_goals   — goals scored average (rolling 10)
          3. xg_diff          — home_avg - away_avg
          4. home_form        — win rate last 7 matches (0.0–1.0)
          5. away_form        — win rate last 7 matches (0.0–1.0)
          6. home_momentum    — streak score last 3 matches (+/-0.2)
          7. away_momentum    — streak score last 3 matches (+/-0.2)
        """
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            print("Kayitli model yukleniyor (model.pkl)...")
            mlp = joblib.load(MODEL_PATH)
            scaler = joblib.load(SCALER_PATH)
            print("Model basariyla yuklendi!")
            return mlp, scaler
        
        print("Deep Learning modeli gercek mac verileriyle egitiliyor...")
        X, y = [], []

        def _form_score(result_list):
            """Converts a list of results (1=Win,0=Draw,-1=Loss) to form score 0.0-1.0."""
            if not result_list:
                return 0.5
            last7 = result_list[-7:]
            return (sum(1 for r in last7 if r == 1) + sum(0.4 for r in last7 if r == 0)) / len(last7)

        def _momentum(result_list):
            """Last 3 matches momentum: +0.2 for 3W, -0.2 for 3L, else 0.0."""
            if len(result_list) < 3:
                return 0.0
            last3 = result_list[-3:]
            if all(r == 1 for r in last3):
                return 0.2
            if all(r == -1 for r in last3):
                return -0.2
            return 0.0

        try:
            url = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                df = df.dropna(subset=['home_score', 'away_score'])
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df[df['date'] >= '2005-01-01'].sort_values('date').reset_index(drop=True)
                
                goal_hist   = {}   # team → list of goals scored
                result_hist = {}   # team → list of 1/0/-1 (win=1, draw=0, loss=-1)
                
                for _, row in df.iterrows():
                    home, away  = row['home_team'], row['away_team']
                    hs, aws = float(row['home_score']), float(row['away_score'])
                    
                    h_avg  = float(np.mean(goal_hist.get(home, [1.4])))
                    a_avg  = float(np.mean(goal_hist.get(away, [1.4])))
                    h_form = _form_score(result_hist.get(home, []))
                    a_form = _form_score(result_hist.get(away, []))
                    h_mom  = _momentum(result_hist.get(home, []))
                    a_mom  = _momentum(result_hist.get(away, []))
                    
                    X.append([h_avg, a_avg, h_avg - a_avg, h_form, a_form, h_mom, a_mom])
                    
                    if hs > aws:
                        y.append(1)
                        h_res, a_res = 1, -1
                    elif hs == aws:
                        y.append(0)
                        h_res, a_res = 0, 0
                    else:
                        y.append(2)
                        h_res, a_res = -1, 1
                    
                    # Update histories (rolling last 10 for goals, last 10 for results)
                    for team, g, res in [(home, hs, h_res), (away, aws, a_res)]:
                        goal_hist.setdefault(team, []).append(g)
                        goal_hist[team] = goal_hist[team][-10:]
                        result_hist.setdefault(team, []).append(res)
                        result_hist[team] = result_hist[team][-10:]
                
                print(f"  Gercek veri: {len(X)} mac, 7 ozellik kullanildi.")
        except Exception as e:
            print(f"  Veri cekilemedi, fallback: {e}")
        
        # Fallback
        if len(X) < 100:
            np.random.seed(42)
            n = 10000
            h = np.random.uniform(0.5, 3.5, n)
            a = np.random.uniform(0.5, 3.5, n)
            hf = np.random.uniform(0.3, 1.0, n)
            af = np.random.uniform(0.3, 1.0, n)
            hm = np.random.choice([-0.2, 0, 0.2], n)
            am = np.random.choice([-0.2, 0, 0.2], n)
            X = np.column_stack((h, a, h-a, hf, af, hm, am)).tolist()
            y = []
            for i in range(n):
                hg = np.random.poisson(h[i] * (0.85 + hf[i]*0.3) * (1 + hm[i]*0.5))
                ag = np.random.poisson(a[i] * (0.85 + af[i]*0.3) * (1 + am[i]*0.5))
                y.append(1 if hg > ag else (0 if hg == ag else 2))

        X = np.array(X)
        y = np.array(y)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Larger network since we have more features
        mlp = MLPClassifier(hidden_layer_sizes=(128, 64, 32), max_iter=500, random_state=42)
        mlp.fit(X_scaled, y)
        
        joblib.dump(mlp, MODEL_PATH)
        joblib.dump(scaler, SCALER_PATH)
        print(f"  Model kaydedildi: {MODEL_PATH}")
        print(f"  Sinir agi egitimi tamamlandi.")
        return mlp, scaler

    def calculate_probabilities(self, home_team, away_team, home_injuries=None, away_injuries=None):
        """
        Hybrid prediction: Elo-based formula (primary) + API-Football adjustments + Injury penalties.
        
        1. Elo difference → calibrated Win/Draw/Loss base probabilities
           (same formula as FIFA, ClubElo, professional bookmakers)
        2. API-Football form & momentum → ±10-15% fine-tuning
        3. Injury tracking via iddaa.com + PlayerRater -> Penalty scaling
        
        This prevents neural-network miscalibration on club vs international data.
        """
        if home_injuries is None: home_injuries = []
        if away_injuries is None: away_injuries = []
        
        home_stats = self.data_fetcher.get_team_stats(home_team)
        away_stats = self.data_fetcher.get_team_stats(away_team)
        
        home_team_id = home_stats.get('team_id')
        away_team_id = away_stats.get('team_id')

        # Iddaa scraping iptal edildigi icin, fallback olarak Transfermarkt uzerinden sakatlari cekeriz
        if not home_injuries:
            home_injuries = self.data_fetcher.get_transfermarkt_injuries(home_team)
            
        if not away_injuries:
            away_injuries = self.data_fetcher.get_transfermarkt_injuries(away_team)

        # ── Elo-based base probabilities ──────────────────────────────
        elo_h = home_stats.get('elo')
        elo_a = away_stats.get('elo')
        
        # If we cannot find real Elo ratings, we explicitly skip the match
        # rather than assigning a default 1400 which leads to massive false edges.
        if elo_h is None or elo_a is None:
            return None
            
        elo_h = float(elo_h)
        elo_a = float(elo_a)
        
        # 30 Elo points ≈ home field advantage in football (previously 100, which was too high)
        elo_diff = elo_h - elo_a + 30
        
        # Standard Elo win probability (logistic function, base 10, scale 400)
        p_home_elo = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
        
        # Draw probability: peaks around Elo equality, decreases for large differences
        abs_diff = abs(elo_h - elo_a)
        p_draw_elo = max(0.08, 0.28 - 0.12 * (abs_diff / 400.0))
        
        # Normalise the three outcomes to 1.0
        p_away_elo = max(0.02, 1.0 - p_home_elo - p_draw_elo)
        # Re-normalise in case of floating point drift
        total = p_home_elo + p_draw_elo + p_away_elo
        p_home_elo /= total
        p_draw_elo /= total
        p_away_elo /= total

        # ── API-Football adjustments (form & momentum) ────────────────
        home_form = float(home_stats.get('form', 0.5))      # 0.0-1.0
        away_form = float(away_stats.get('form', 0.5))
        home_mom  = float(home_stats.get('momentum', 0.0))  # -0.2 to +0.2
        away_mom  = float(away_stats.get('momentum', 0.0))

        # Form edge: difference in form shifts pHome vs pAway (much smaller impact now)
        form_delta = (home_form - away_form) * 0.03  # Max ±3% swing
        mom_delta  = (home_mom - away_mom) * 0.05    # Max ±5% swing

        # form and momentum are now handled in the adjustment later

        # ── Injury Modifiers (API-Football current injuries + PlayerRater) ───────
        home_penalty = 0.0
        home_injury_names = []
        for inj in home_injuries:
            rating_data = self.player_rater.get_player_rating(inj, home_team_id)
            w = rating_data.get('impact_weight', 0.02)
            home_penalty += w
            home_injury_names.append(f"{inj} ({rating_data.get('impact_category')})")
            
        away_penalty = 0.0
        away_injury_names = []
        for inj in away_injuries:
            rating_data = self.player_rater.get_player_rating(inj, away_team_id)
            w = rating_data.get('impact_weight', 0.02)
            away_penalty += w
            away_injury_names.append(f"{inj} ({rating_data.get('impact_category')})")
            
        # The penalty reduces a team's win probability directly and shifts it to the opponent
        # Example: Home drops by 10% because of injuries, so p_home -= 0.10, p_away += 0.05, p_draw += 0.05
        
        p_home = p_home_elo + form_delta + mom_delta
        p_away = p_away_elo - form_delta - mom_delta
        
        # Apply injuries heavily but don't exceed -20% max penalty per team
        home_penalty = min(0.20, home_penalty)
        away_penalty = min(0.20, away_penalty)
        
        # Cross-adjust
        p_home = p_home * (1.0 - home_penalty) + p_away * away_penalty * 0.5
        p_away = p_away * (1.0 - away_penalty) + p_home_elo * home_penalty * 0.5 # use original to avoid loop drift
        p_draw = 1.0 - p_home - p_away

        # Clamp to avoid negative probabilities
        p_home = max(0.02, min(0.95, p_home))
        p_away = max(0.02, min(0.95, p_away))
        p_draw = max(0.02, min(0.50, p_draw))

        # Final normalise
        total = p_home + p_draw + p_away
        p_home /= total
        p_draw /= total
        p_away /= total

        # xG for display / explanation purposes
        home_xg = (home_stats['avg_goals_scored'] + away_stats['avg_goals_conceded']) / 2 * 1.05
        away_xg = (away_stats['avg_goals_scored'] + home_stats['avg_goals_conceded']) / 2
        home_xg = max(0.4, min(4.0, home_xg))
        away_xg = max(0.4, min(4.0, away_xg))

        return {
            '1': round(p_home, 3),
            'X': round(p_draw, 3),
            '2': round(p_away, 3),
            'Home_xG': round(home_xg, 2),
            'Away_xG': round(away_xg, 2),
            'Home_Elo': int(elo_h),
            'Away_Elo': int(elo_a),
            'Home_Form': round(home_form, 2),
            'Away_Form': round(away_form, 2),
            'Home_Mom': round(home_mom, 2),
            'Away_Mom': round(away_mom, 2),
            'Home_Penalty_Pct': round(home_penalty * 100, 1),
            'Away_Penalty_Pct': round(away_penalty * 100, 1),
            'Home_Missing_Strs': home_injury_names,
            'Away_Missing_Strs': away_injury_names,
            'AI_Type': 'Elo + API-Football (Form/Momentum)'
        }

if __name__ == "__main__":
    from data_fetcher import HistoricalDataFetcher
    fetcher = HistoricalDataFetcher()
    predictor = Predictor(fetcher)
    probs = predictor.calculate_probabilities("Galatasaray", "Fenerbahce")
    print("Sonuclar (Galatasaray vs Fenerbahce):", probs)



