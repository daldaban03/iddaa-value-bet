import pandas as pd
from scraper import IddaaScraper
from predictor import Predictor
from data_fetcher import HistoricalDataFetcher
    
print("Starting live test...")
scraper = IddaaScraper()
print("Fetching bulletin...")
df = scraper.fetch_daily_bulten()
    
print(f"Extracted {len(df)} matches. Initializing Predictor...")
fetcher = HistoricalDataFetcher()
predictor = Predictor(fetcher)
    
print(f"Columns: {df.columns.tolist()}")

for index, row in df.iterrows():
    # Find home/away column flexibly
    home_col = next((c for c in df.columns if 'home' in c.lower()), None)
    away_col = next((c for c in df.columns if 'away' in c.lower()), None)
    
    home_team = row[home_col] if home_col else None
    away_team = row[away_col] if away_col else None
    
    if not home_team or not away_team:
        print("Cannot find team columns")
        break
        
    print(f"\nAnalyzing: {home_team} vs {away_team}")
    probs = predictor.calculate_probabilities(home_team, away_team)
    if probs:
        print(f"  Probs: Home {probs['home_win']:.2f}, Draw {probs['draw']:.2f}, Away {probs['away_win']:.2f}")
    else:
        print("  Could not generate probabilities (missing data).")
    break # Only do 1 match to trace bug
print("Done.")
