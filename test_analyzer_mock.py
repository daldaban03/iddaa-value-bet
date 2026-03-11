import pandas as pd
from analyzer import ValueAnalyzer

class MockPredictor:
    def calculate_probabilities(self, h, a):
        return {
            '1': 0.60, 'X': 0.25, '2': 0.15,
            'Home_xG': 2.1, 'Away_xG': 0.9,
            'Home_Elo': 1700, 'Away_Elo': 1500,
            'Home_Form': 0.8, 'Away_Form': 0.4,
            'Home_Mom': 0.2, 'Away_Mom': -0.2,
            'Home_Penalty_Pct': 0.0, 'Away_Penalty_Pct': 0.0,
            'Home_Missing_Strs': [], 'Away_Missing_Strs': []
        }

analyzer = ValueAnalyzer(MockPredictor())
df = pd.DataFrame([{
    'Date': '2026-03-11',
    'Match': 'A vs B',
    'Home_Team': 'A',
    'Away_Team': 'B',
    'Odds_1': 2.00,
    'Odds_X': 3.50,
    'Odds_2': 4.00
}])

print(analyzer.analyze_fixtures(df, min_edge=0.05))
