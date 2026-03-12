import pandas as pd
import math

class ValueAnalyzer:
    def __init__(self, predictor):
        self.predictor = predictor

    def calculate_expected_value(self, prob, odds):
        """
        Calculates Expected Value (EV)
        EV = (Probability * Decimal Odds) - 1
        If EV > 0, the bet is mathematically profitable long term.
        """
        return (prob * odds) - 1.0

    def kelly_fraction(self, prob, odds, fraction=0.50):
        """
        Kelly Criterion: f* = (bp - q) / b
        where b = odds - 1, p = win probability, q = 1 - p
        fraction: Kelly fraction (0.50 = half-Kelly = high risk)
        Returns fraction of bankroll to bet.
        """
        b = odds - 1.0
        q = 1.0 - prob
        if b <= 0:
            return 0.0
        kelly = (b * prob - q) / b
        return max(0.0, kelly * fraction)

    def analyze_fixtures(self, bulten_df, min_edge=0.05, bankroll=100000):
        """
        Analyzes a DataFrame of fixtures and returns a DataFrame containing
        Value Bets (cases where EV > min_edge).
        """
        results = []

        for index, row in bulten_df.iterrows():
            
            probs = self.predictor.calculate_probabilities(
                row['Home_Team'], 
                row['Away_Team']
            )
            
            # Skip match if predictor couldn't generate probabilities (e.g. missing Elo)
            if probs is None:
                continue
                
            # Handle explicit skips (e.g., missing genuine ClubElo ratings)
            if 'Skip_Reason' in probs:
                print(f"  [Analyzer] Skipping match {row['Home_Team']} vs {row['Away_Team']}: {probs['Skip_Reason']}")
                continue
                
            home_xg = probs.get('Home_xG', 0)
            away_xg = probs.get('Away_xG', 0)
            
            # Extract raw stats from predictor for explanation
            home_elo = probs.get('Home_Elo', '?')
            away_elo = probs.get('Away_Elo', '?')
            home_form = probs.get('Home_Form', '?')
            away_form = probs.get('Away_Form', '?')
            home_mom = probs.get('Home_Mom', '?')
            away_mom = probs.get('Away_Mom', '?')
            
            # New Injury Data
            h_miss_strs = probs.get('Home_Missing_Strs', [])
            a_miss_strs = probs.get('Away_Missing_Strs', [])
            h_pen = probs.get('Home_Penalty_Pct', 0.0)
            a_pen = probs.get('Away_Penalty_Pct', 0.0)
            
            h_names = ", ".join(h_miss_strs) if h_miss_strs else "Yok"
            a_names = ", ".join(a_miss_strs) if a_miss_strs else "Yok"
            inj_str = f"Ev Eksikleri ({len(h_miss_strs)}): {h_names}\n> Dep. Eksikleri ({len(a_miss_strs)}): {a_names}"
            pen_str = f"Ev Ceza: -%{h_pen}, Dep Ceza: -%{a_pen}"
            
            h_inj_count = len(h_miss_strs)
            a_inj_count = len(a_miss_strs)
            
            reliability = probs.get('Reliability', 'Low')
            r_flags = probs.get('Reliability_Flags', [])
            
            # Check Home Win (1)
            ev_1 = self.calculate_expected_value(probs['1'], row['Odds_1'])
            if ev_1 >= min_edge:
                kelly_f = self.kelly_fraction(probs['1'], row['Odds_1'])
                kelly_bet = round(bankroll * kelly_f, 0)
                results.append(self._create_result_row(
                    row, '1 (Ev Sahibi)', probs['1'], row['Odds_1'], ev_1,
                    home_xg, away_xg, home_elo, away_elo, home_form, away_form,
                    home_mom, away_mom, inj_str, pen_str, h_inj_count, a_inj_count,
                    kelly_f, kelly_bet, reliability, r_flags
                ))

            # Check Draw (X)
            ev_x = self.calculate_expected_value(probs['X'], row['Odds_X'])
            if ev_x >= min_edge:
                kelly_f = self.kelly_fraction(probs['X'], row['Odds_X'])
                kelly_bet = round(bankroll * kelly_f, 0)
                results.append(self._create_result_row(
                    row, 'X (Beraberlik)', probs['X'], row['Odds_X'], ev_x,
                    home_xg, away_xg, home_elo, away_elo, home_form, away_form,
                    home_mom, away_mom, inj_str, pen_str, h_inj_count, a_inj_count,
                    kelly_f, kelly_bet, reliability, r_flags
                ))

            # Check Away Win (2)
            ev_2 = self.calculate_expected_value(probs['2'], row['Odds_2'])
            if ev_2 >= min_edge:
                kelly_f = self.kelly_fraction(probs['2'], row['Odds_2'])
                kelly_bet = round(bankroll * kelly_f, 0)
                results.append(self._create_result_row(
                    row, '2 (Deplasman)', probs['2'], row['Odds_2'], ev_2,
                    home_xg, away_xg, home_elo, away_elo, home_form, away_form,
                    home_mom, away_mom, inj_str, pen_str, h_inj_count, a_inj_count,
                    kelly_f, kelly_bet, reliability, r_flags
                ))

        # Convert to DataFrame and sort by Expected Value (highest first)
        results_df = pd.DataFrame(results)
        if not results_df.empty:
            results_df = results_df.sort_values(by='Expected_Value', ascending=False)
            
        return results_df

    def build_coupon(self, value_bets_df, bankroll=100000, max_singles=5, max_system_legs=4):
        """
        Builds an optimal coupon from value bets using Kelly Criterion.
        Returns:
            singles: list of single bet recommendations
            system_coupon: system coupon recommendation (if applicable)
            total_stake: total amount to stake
        """
        if value_bets_df.empty:
            return [], None, 0
        
        singles = []
        system_legs = []
        total_stake = 0
        used_matches = set()
        
        for idx, row in value_bets_df.iterrows():
            match_name = row['Match']
            if match_name in used_matches:
                continue
                
            bet = {
                'match': match_name,
                'prediction': row['Prediction'],
                'odds': row['Iddaa_Odds'],
                'ai_prob': row['AI_Probability'],
                'edge': row['Edge'],
                'kelly_bet': row['Kelly_Bahis'],
                'kelly_pct': row['Kelly_Pct'],
                'ev_eksik': row['Ev_Eksik'],
                'dep_eksik': row['Dep_Eksik'],
            }
            
            used_matches.add(match_name)
            
            if len(singles) < max_singles:
                singles.append(bet)
                total_stake += float(str(bet['kelly_bet']).replace(',', ''))
            
            # Candidates for system coupon
            prob_val = float(row['AI_Probability'].replace('%', '')) / 100
            if len(system_legs) < max_system_legs:
                system_legs.append(bet)
        
        # Build system coupon if we have enough legs
        system_coupon = None
        if len(system_legs) >= 2:
            combined_odds = 1.0
            combined_prob = 1.0
            for leg in system_legs:
                combined_odds *= leg['odds']
                prob_val = float(leg['ai_prob'].replace('%', '')) / 100
                combined_prob *= prob_val
            
            # System coupon stake: quarter-Kelly on combined
            system_ev = combined_prob * combined_odds - 1.0
            if system_ev > 0:
                system_kelly = self.kelly_fraction(combined_prob, combined_odds, fraction=0.15)
                system_stake = round(bankroll * system_kelly, 0)
                system_stake = max(5, min(system_stake, bankroll * 0.05))  # Cap at 5% of bankroll
                
                import math
                n = len(system_legs)
                is_full_system = n <= 3
                k = n if is_full_system else n - 1
                combinations = math.comb(n, k)
                
                # The calculated system stake is treated as the "Total Stake" for the coupon
                # So we deduce the per-column stake from it
                total_stake = system_stake
                per_column_stake = system_stake / combinations
                
                # E.g. "50 TL (150 TL)"
                formatted_stake = f"{per_column_stake:,.0f} TL ({total_stake:,.0f} TL)"
                
                system_coupon = {
                    'legs': system_legs,
                    'combined_odds': round(combined_odds, 2),
                    'combined_prob': f"{combined_prob*100:.1f}%",
                    'system_ev': f"{system_ev*100:.1f}%",
                    'stake': total_stake,  # keep for potential math in UI
                    'formatted_stake': formatted_stake,
                    'potential_win': round(total_stake * combined_odds, 0),
                    'type': f"{k}/{n} Sistem"
                }
        
        return singles, system_coupon, total_stake

    def _create_result_row(self, fixture_row, prediction_type, prob, odds, ev,
                           home_xg, away_xg, home_elo, away_elo, home_form, away_form,
                           home_mom, away_mom, inj_str, pen_str, h_inj_count, a_inj_count,
                           kelly_f, kelly_bet, reliability, r_flags):
        
        rel_icon = "🟢 Yüksek" if reliability == "High" else ("🟡 Orta" if reliability == "Medium" else "🔴 Düşük")
        flags_str = ", ".join(r_flags) if r_flags else "Tümü Orijinal Kaynak"
        
        explanation = (
            f"[Veri Kalitesi]: {rel_icon} ({flags_str})\n\n"
            f"[Adim 1 - Poisson xG Modeli] Lig istatistiklerinden hesaplanan beklenen gol (xG): "
            f"{fixture_row['Home_Team']}: {home_xg} gol / {fixture_row['Away_Team']}: {away_xg} gol.\n\n"
            f"[Adim 2 - Yapay Zeka (Poisson + XGBoost/MLP + Elo)] '{fixture_row['Home_Team']}' (Elo: {home_elo}, Form: {home_form}/1.0, Ivme: {home_mom}) ve "
            f"'{fixture_row['Away_Team']}' (Elo: {away_elo}, Form: {away_form}/1.0, Ivme: {away_mom}) verilerine iliskin oyuncu eksikleri su sekilde: \n"
            f"> {inj_str}\n"
            f"> Yapay Zeka Oran Cezasi: {pen_str}\n\n"
            f"Transfermarkt verilerine gore eksik oyuncularin guncel piyasa degerleri paha olarak takim kadrosuna oranlanmis, tahribat yuzdesi buna gore dinamik dusurulmustur.\n"
            f"Tum bu veriler dogrultusunda '{prediction_type}' sonucunun olasiligi %{prob*100:.1f} olarak hesaplandi.\n\n"
            f"[Adim 3 - Value (Deger) Testi] Iddaa'nin actigi {odds} orani, yapay zekanin bu dinamik guncel verilerden buldugu %{prob*100:.1f} gercek ihtimaliyle karsilastirildi.\n\n"
            f"[Adim 4 - Kelly Kriteri] Sermaye: 100.000 TL | Onerilen bahis: {kelly_bet:,.0f} TL (Kelly: %{kelly_f*100:.2f})\n\n"
            f"[Sonuc] (%{prob*100:.1f} x {odds}) - 1 = Edge (Avantaj) %{ev*100:.1f} --> Matematiksel olarak karli bahis!"
        )
        return {
            'Date': fixture_row['Date'],
            'Match': f"{fixture_row['Home_Team']} vs {fixture_row['Away_Team']}",
            'Prediction': prediction_type,
            'AI_Probability': f"{prob*100:.1f}%",
            'Iddaa_Odds': odds,
            'Veri_Kalitesi': rel_icon,
            'Expected_Value': round(ev, 3),
            'Edge': f"{ev*100:.1f}%",
            'Ev_Eksik': h_inj_count,
            'Dep_Eksik': a_inj_count,
            'Kelly_Pct': f"%{kelly_f*100:.2f}",
            'Kelly_Bahis': f"{kelly_bet:,.0f}",
            'Explanation': explanation
        }

if __name__ == "__main__":
    from scraper import IddaaScraper
    from data_fetcher import HistoricalDataFetcher
    from predictor import Predictor
    
    # Simple test flow
    scraper = IddaaScraper()
    fetcher = HistoricalDataFetcher()
    predictor = Predictor(fetcher)
    analyzer = ValueAnalyzer(predictor)
    
    bulten = scraper.fetch_daily_bulten()
    value_bets = analyzer.analyze_fixtures(bulten)
    
    print("\nFound Value Bets:")
    print(value_bets)
