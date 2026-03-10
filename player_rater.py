import os
import json


CACHE_FILE = os.path.join(os.path.dirname(__file__), "player_cache.json")


class PlayerRater:
    """
    Rates injured player impact using cached knowledge.
    No external API calls — uses simple name-based heuristics and cached data.
    """

    def __init__(self):
        self.cache = self._load_cache()

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

    def get_player_rating(self, player_name, team_name=None):
        """
        Estimate player impact weight based on cached data or default.
        
        Returns dict with:
          - impact_category: 'Yıldız', 'İlk 11', 'Rotasyon'
          - impact_weight: 0.05 / 0.035 / 0.015
        """
        # Check cache
        cache_key = player_name.lower().strip()
        if cache_key in self.cache:
            rating = self.cache[cache_key]
            if isinstance(rating, (int, float)):
                return self._categorize_rating(rating)

        # Default: treat as starter (mid-impact)
        return self._default_rating()

    def _default_rating(self):
        return {
            'rating': 6.8,
            'impact_category': 'İlk 11 (Tahmini)',
            'impact_weight': 0.025
        }

    def _categorize_rating(self, rating):
        """
        Categorize by rating:
        > 7.2: Star / Key Player → 5% penalty
        6.8 - 7.2: Starter → 3% penalty
        < 6.8: Rotation → 1.5% penalty
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
