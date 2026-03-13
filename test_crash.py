import pandas as pd
from analyzer import ValueAnalyzer
import unittest
from unittest.mock import MagicMock

class TestAnalyzer(unittest.TestCase):
    def test_analysis_integrity(self):
        # Mock Predictor
        mock_predictor = MagicMock()
        mock_predictor.calculate_probabilities.return_value = {
            '1': 0.5, 'X': 0.3, '2': 0.2,
            'Home_xG': 1.5, 'Away_xG': 1.0,
            'Home_Elo': 1700, 'Away_Elo': 1600,
            'Home_Form': 0.6, 'Away_Form': 0.5,
            'Home_Mom': 0.0, 'Away_Mom': 0.0,
            'Home_Missing_Strs': ['Player A (Injured)'], 'Away_Missing_Strs': [],
            'Home_Penalty_Pct': 5.0, 'Away_Penalty_Pct': 0.0,
            'Reliability': 'Medium',
            'Reliability_Flags': ['Elo_Ikincil_veya_Tahmini']
        }
        
        analyzer = ValueAnalyzer(mock_predictor)
        
        # Sample Bulletin
        bulten_df = pd.DataFrame([{
            'Home_Team': 'Team A',
            'Away_Team': 'Team B',
            'Odds_1': 2.5,
            'Odds_X': 3.2,
            'Odds_2': 4.0,
            'Date': '2026-03-13 20:00'
        }])
        
        print("Running analyze_fixtures...")
        results = analyzer.analyze_fixtures(bulten_df)
        print("Results generated.")
        
        if not results.empty:
            print("First row explanation preview:")
            print(results.iloc[0]['Explanation'][:100])
        
        print("Running build_coupon...")
        singles, system, total = analyzer.build_coupon(results)
        print(f"Coupon built. Total stake: {total}")

if __name__ == "__main__":
    test = TestAnalyzer()
    test.test_analysis_integrity()
