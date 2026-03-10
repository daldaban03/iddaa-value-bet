import os
import json

class PlayerRater:
    """
    Rates injured player impact using their Transfermarkt market value.
    No longer uses heuristic names, instead calculates percentage drops based on estimated squad worth.
    """

    def __init__(self, default_squad_value_m=150.0):
        # Default typical Top-tier Super Lig or mid-tier Top 5 league squad value (in Millions Euro)
        self.default_squad_value_m = default_squad_value_m

    def get_player_rating(self, player_dict, team_name=None, team_squad_value_m=None):
        """
        Estimate player impact weight based on their market value.
        
        player_dict: {'name': 'Player', 'val_str': '15.00m', 'value_m': 15.0}
        """
        squad_val = team_squad_value_m if team_squad_value_m else self.default_squad_value_m
        val = player_dict.get('value_m', 0.0)
        
        if val <= 0:
            return self._default_rating()

        # Impact logic: player_value / squad_value * multiplier
        # A 50m player in a 200m squad = 25% of the squad's financial worth.
        # We cap a single player's impact at 12.5% (to prevent 1 player tanking chances to 0 too fast).
        raw_ratio = val / squad_val
        impact = raw_ratio * 0.8  # 80% of their financial share translates to win-chances impact
        
        impact = min(0.125, impact) 
        
        # Categorize for UI
        if impact > 0.05:
            cat = 'Yıldız / Kilit'
        elif impact > 0.02:
            cat = 'İlk 11 Oyuncusu'
        else:
            cat = 'Rotasyon / Yedek'

        return {
            'rating': round(val, 1),
            'impact_category': f"{cat} ({player_dict.get('val_str', '')})",
            'impact_weight': round(impact, 3)
        }

    def _default_rating(self):
        """If no value could be parsed, apply a tiny default penalty (1.5%) instead of a big one."""
        return {
            'rating': 0.0,
            'impact_category': 'Bilinmeyen (Tahmini)',
            'impact_weight': 0.015
        }
