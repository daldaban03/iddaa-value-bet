import threading
import time
import json
import os
from datetime import datetime
import pandas as pd
from utils.persistence import save_predictions

# We'll use these for the background analysis
from scraper import IddaaScraper
from data_fetcher import HistoricalDataFetcher
from predictor import Predictor
from analyzer import ValueAnalyzer

LATEST_SCAN_PATH = "data/latest_scan.json"

class BackgroundAnalyzer(threading.Thread):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BackgroundAnalyzer, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, interval_seconds=900):
        if self._initialized:
            return
        super().__init__(name="BackgroundAnalyzerThread", daemon=True)
        self.interval = interval_seconds
        self.running = False
        
        # Start only the scraper synchonously
        self.scraper = IddaaScraper()
        
        # These will be initialized in the background thread to avoid blocking the UI
        self.fetcher = None
        self.predictor = None
        self.analyzer = None
        
        # Default settings for background scan
        self.bankroll = 100000
        self.min_edge = 0.15
        self.risk_fraction = 0.5
        
        self._initialized = True

    def run(self):
        self.running = True
        print("[BackgroundWorker] Thread started. Initializing heavy components in background...")
        try:
            self.fetcher = HistoricalDataFetcher()
            self.predictor = Predictor(self.fetcher)
            self.analyzer = ValueAnalyzer(self.predictor)
            print("[BackgroundWorker] Heavy components initialized successfully.")
        except Exception as e:
            print(f"[BackgroundWorker] FAILED to initialize components: {e}")
            self.running = False
            return

        while self.running:
            try:
                self.perform_scan()
            except Exception as e:
                print(f"[BackgroundWorker] Error during scan: {e}")
            
            print(f"[BackgroundWorker] Sleeping for {self.interval} seconds...")
            time.sleep(self.interval)

    def perform_scan(self):
        if not self.analyzer:
            return
            
        print(f"[BackgroundWorker] Starting analysis cycle at {datetime.now()}...")
        
        # 1. Fetch Bulletin
        bulten_df = self.scraper.fetch_daily_bulten()
        if bulten_df.empty:
            print("[BackgroundWorker] Bulletin is empty, skipping cycle.")
            return

        # 2. Analyze
        value_bets_df = self.analyzer.analyze_fixtures(
            bulten_df,
            min_edge=self.min_edge,
            bankroll=self.bankroll,
            kelly_fraction=self.risk_fraction
        )
        
        # 3. Save as latest scan
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = {
            "last_scan": timestamp,
            "bankroll": self.bankroll,
            "risk_fraction": self.risk_fraction,
            "predictions": value_bets_df.to_dict(orient="records") if not value_bets_df.empty else [],
            "bulten": bulten_df.to_dict(orient="records") if not bulten_df.empty else []
        }
        
        os.makedirs(os.path.dirname(LATEST_SCAN_PATH), exist_ok=True)
        with open(LATEST_SCAN_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        # Also save to archived predictions
        save_predictions(value_bets_df, self.bankroll, self.risk_fraction, self.min_edge * 100)
        
        print(f"[BackgroundWorker] Cycle complete. Found {len(value_bets_df)} value bets.")

    def stop(self):
        self.running = False

def get_latest_scan():
    if os.path.exists(LATEST_SCAN_PATH):
        try:
            with open(LATEST_SCAN_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None
