import requests
import json
import os

CACHE_FILE = os.path.join(os.path.dirname(__file__), "player_cache.json")
API_FOOTBALL_KEY = "ace5b148be95024d291c774edcd33e10"
API_FOOTBALL_URL = "https://v3.football.api-sports.io"

class PlayerRater:
    def __init__(self):
        self.cache = self._load_cache()
        self.api_headers = {'x-apisports-key': API_FOOTBALL_KEY}

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Cache save error:", e)

    def get_player_rating(self, player_name, team_id, season="2024"):
        """
        Retrieves live player performance rating (1.0 - 10.0) via API-Football.
        We fetch the whole squad once per team and cache ALL players to severely reduce API calls (which are limited).
        """
        # Cache key based on team to avoid calling API for each missing player individually
        cache_key = f"squad_{team_id}_{season}"
        
        # 1. Fetch and cache the entire squad if not present
        if cache_key not in self.cache:
            try:
                r = requests.get(
                    f"{API_FOOTBALL_URL}/players", 
                    headers=self.api_headers, 
                    params={"team": team_id, "season": season},
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    players = data.get('response', [])
                    
                    team_squad = {}
                    for p in players:
                        pl_info = p.get('player', {})
                        name = pl_info.get('name', 'Unknown')
                        stats = p.get('statistics', [])
                        
                        rating = None
                        if stats:
                            games = stats[0].get('games', {})
                            rating_str = games.get('rating')
                            if rating_str:
                                try:
                                    rating = float(rating_str)
                                except:
                                    pass
                        team_squad[name.lower()] = rating
                        
                    self.cache[cache_key] = team_squad
                    self._save_cache()
                else:
                    print(f"Failed to fetch squad for team {team_id}: HTTP {r.status_code}")
                    self.cache[cache_key] = {} # Prevent endless retrying
            except Exception as e:
                print(f"Exception fetching squad {team_id}: {e}")
                self.cache[cache_key] = {}
                return self._default_rating()
                
        # 2. Look up the specific player in the cached squad
        squad = self.cache.get(cache_key, {})
        
        # Exact match
        rating = squad.get(player_name.lower())
        
        # Fuzzy match (since names from iddaa might be 'M. Icardi' instead of 'Mauro Icardi')
        if rating is None:
            for cached_name, cached_rating in squad.items():
                if player_name.lower() in cached_name or cached_name in player_name.lower():
                    rating = cached_rating
                    break
                    
        return self._categorize_rating(rating)
        
    def _default_rating(self):
        return {
            'rating': 6.8, 
            'impact_category': 'Rotasyon / Yedek (Bilinmiyor)',
            'impact_weight': 0.02 # 2% penalty
        }
        
    def _categorize_rating(self, rating):
        """
        Categorizes standard 1-10 football ratings:
        > 7.2 : Star / Key Player (Massive impact) => 5% penalty
        6.8 - 7.2 : Starter / Good -> 3.5% penalty
        < 6.8 or None : Bench / Rotation -> 1.5% penalty
        """
        if rating is None:
            return self._default_rating()
            
        result = {'rating': round(rating, 2)}
        
        if rating >= 7.20:
            result['impact_category'] = 'Yıldız / Kilit Oyuncu'
            result['impact_weight'] = 0.05
        elif rating >= 6.80:
            result['impact_category'] = 'İlk 11 Oyuncusu'
            result['impact_weight'] = 0.035
        else:
            result['impact_category'] = 'Rotasyon / Yedek'
            result['impact_weight'] = 0.015
            
        return result
