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
