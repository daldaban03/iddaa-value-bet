import json
import os
from datetime import datetime, timezone, timedelta
import pandas as pd

PREDICTIONS_DIR = "data/predictions"

def save_predictions(df, bankroll, risk_fraction, min_edge):
    """
    Saves the analyzed value bets to a JSON file for future performance tracking.
    """
    if df.empty:
        return None
        
    if not os.path.exists(PREDICTIONS_DIR):
        os.makedirs(PREDICTIONS_DIR, exist_ok=True)
        
    # Turkey Time (UTC+3)
    trt = timezone(timedelta(hours=3))
    timestamp = datetime.now(trt).strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_analysis.json"
    filepath = os.path.join(PREDICTIONS_DIR, filename)
    
    # Metadata for the analysis session
    metadata = {
        "timestamp": timestamp,
        "bankroll": bankroll,
        "risk_fraction": risk_fraction,
        "min_edge": min_edge,
    }
    
    # Prepare data for saving (convert to dict)
    predictions = df.to_dict(orient="records")
    
    data = {
        "metadata": metadata,
        "predictions": predictions
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    return filepath

def update_prediction_results(fetcher):
    """
    Scans archived prediction files and updates 'Pending' matches with official results.
    """
    if not os.path.exists(PREDICTIONS_DIR):
        return 0
        
    import glob
    files = glob.glob(os.path.join(PREDICTIONS_DIR, "*.json"))
    updated_count = 0
    
    for f in files:
        changed = False
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
            
            # Skip if it's already fully verified or not in the right format
            if 'predictions' not in data:
                continue
                
            for pred in data['predictions']:
                # Only check matches that are currently pending
                current_status = pred.get('Status', '⏳ Beklemede')
                if "Beklemede" in current_status or "Bekleniyor" in current_status:
                    match_name = pred.get('Match', '')
                    if ' vs ' not in match_name:
                        continue
                        
                    home, away = match_name.split(' vs ')
                    
                    # Search for teams in league data
                    l_code, h_canon, df, _ = fetcher._find_team_in_leagues(home)
                    _, a_canon, _, _ = fetcher._find_team_in_leagues(away)
                    
                    if h_canon and a_canon and df is not None:
                        # Look for this specific fixture in history
                        mask = (df['HomeTeam'] == h_canon) & (df['AwayTeam'] == a_canon)
                        match_row = df[mask]
                        
                        if not match_row.empty:
                            fthg = match_row.iloc[0].get('FTHG')
                            ftag = match_row.iloc[0].get('FTAG')
                            ftr = match_row.iloc[0].get('FTR')
                            
                            if pd.notna(ftr):
                                score_str = f"{int(fthg)}-{int(ftag)} ({ftr})"
                                pred['Result'] = score_str
                                
                                # Check win/loss
                                pred_type = pred['Prediction'].split(' ')[0]
                                is_won = False
                                if (pred_type == '1' and ftr == 'H') or \
                                   (pred_type == 'X' and ftr == 'D') or \
                                   (pred_type == '2' and ftr == 'A'):
                                    is_won = True
                                
                                pred['Status'] = "✅ Kazandı" if is_won else "❌ Kaybetti"
                                changed = True
            
            if changed:
                with open(f, "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                updated_count += 1
                
        except Exception as e:
            print(f"Error updating file {f}: {e}")
            
    return updated_count
