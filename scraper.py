import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import uuid
import json
from bs4 import BeautifulSoup

class IddaaScraper:
    def __init__(self):
        # Using official iddaa API to get real Turkish odds including "Kral Oran"
        self.api_url = "https://sportsbookv2.iddaa.com/sportsbook/events?st=1&type=0&version=0"
        self.headers = {
            'referer': 'https://www.iddaa.com/',
            'client-transaction-id': str(uuid.uuid4()),
            'platform': 'web',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
    def fetch_daily_bulten(self):
        """
        Fetches the current football bulletin from iddaa.com API.
        Returns all MBS 1 (Tek Maç) fixtures, sorted by match time ascending.
        """

        match_data = []
        # Turkey Time (UTC+3)
        trt = timezone(timedelta(hours=3))
        today_str = datetime.now(trt).strftime("%Y-%m-%d")
        
        try:
            response = requests.get(self.api_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                events = data.get('data', {}).get('events', [])
                
                for event in events:
                    # Sadece tek maç (MBS 1) olanları al
                    if event.get('mbc') != 1:
                        continue
                        
                    event_id = event.get('ei')
                    home_team = event.get('hn')
                    away_team = event.get('an')
                    is_kral_oran = event.get('kOdd', False)
                    match_time_ms = event.get('d', 0)
                    match_date_str = today_str
                    if match_time_ms:
                        # Convert timestamp to readable date/time (iddaa sends it in seconds)
                        match_date_str = datetime.fromtimestamp(match_time_ms).strftime('%Y-%m-%d %H:%M')
                    
                    # Find Match Result market (t: 1, st: 1)
                    match_odds = None
                    for market in event.get('m', []):
                        if market.get('t') == 1 and market.get('st') == 1:
                            match_odds = market.get('o', [])
                            break
                    
                    if match_odds and len(match_odds) >= 3:
                        # Extract outcomes by name '1', '0', '2'
                        # Use 'odd' if available for Kral Oran, fallback to 'wodd'
                        odds_1 = next((o.get('odd') or o.get('wodd') for o in match_odds if o.get('n') == '1'), None)
                        odds_X = next((o.get('odd') or o.get('wodd') for o in match_odds if o.get('n') == '0'), None)
                        odds_2 = next((o.get('odd') or o.get('wodd') for o in match_odds if o.get('n') == '2'), None)
                        
                        if odds_1 and odds_X and odds_2:
                            
                            match_data.append({
                                'Event_Id': event_id,
                                'Date': match_date_str,
                                'Home_Team': home_team if home_team else "Unknown",
                                'Away_Team': away_team if away_team else "Unknown",
                                'Odds_1': float(odds_1),
                                'Odds_X': float(odds_X),
                                'Odds_2': float(odds_2),
                                'Kral_Oran': 'Evet' if is_kral_oran else 'Hayır',
                            })
                            
                # Sort by match date (earliest first)
                match_data.sort(key=lambda x: x['Date'])
                print(f"Toplam {len(match_data)} Tek Mac (MBS 1) basariyla cekendi.")

            else:
                print(f"Bülten çekilirken hata oluştu: Durum Kodu {response.status_code}")
                
        except Exception as e:
            print(f"Bülten çekme hatası: {e}")
            
        return pd.DataFrame(match_data, columns=['Event_Id', 'Date', 'Home_Team', 'Away_Team', 'Odds_1', 'Odds_X', 'Odds_2', 'Kral_Oran'])

if __name__ == "__main__":
    scraper = IddaaScraper()
    df = scraper.fetch_daily_bulten()
    print("Test: Canlı Bülten")
    print(df.head())
