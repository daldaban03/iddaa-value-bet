import pandas as pd
import requests
import io
import unicodedata
from bs4 import BeautifulSoup

API_FOOTBALL_KEY = "ace5b148be95024d291c774edcd33e10"
API_FOOTBALL_URL = "https://v3.football.api-sports.io"

class HistoricalDataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.api_headers = {'x-apisports-key': API_FOOTBALL_KEY}
        # Cache team IDs and stats to avoid duplicate API calls (limited to 100/day)
        self._team_id_cache = {}
        self._stats_cache = {}
        self._team_league_season_cache = {}
        
        # Transfermarkt caching
        self._tm_injury_links = {}
        self._tm_links_fetched = False

    def _get_team_id(self, team_name):
        """Search API-Football for a team by name, return its numeric ID."""
        if team_name in self._team_id_cache:
            return self._team_id_cache[team_name]
        try:
            r = self.session.get(
                f"{API_FOOTBALL_URL}/teams",
                headers=self.api_headers,
                params={"name": team_name},
                timeout=7
            )
            if r.status_code == 200:
                teams = r.json().get('response', [])
                if teams:
                    team_id = teams[0]['team']['id']
                    self._team_id_cache[team_name] = team_id
                    return team_id
            else:
                print(f"API Error ({r.status_code}) fetching team ID for {team_name}: {r.text}")
        except Exception as e:
            print(f"Exception fetching team ID for {team_name}: {e}")
        return None
    def _fetch_tm_links(self):
        """Fetches the Transfermarkt Super Lig table to cache injury links for all teams."""
        if self._tm_links_fetched:
            return
            
        url = "https://www.transfermarkt.com.tr/super-lig/startseite/wettbewerb/TR1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        try:
            r = self.session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                tables = soup.find_all('table', class_='items')
                if tables:
                    for td in tables[0].find_all('td', class_='hauptlink'):
                        a_tag = td.find('a')
                        if a_tag and '/startseite/verein/' in a_tag.get('href', ''):
                            team_name = a_tag.text.strip()
                            href = a_tag['href']
                            parts = href.split('/')
                            if len(parts) > 4:
                                slug = parts[1]
                                team_id = parts[4]
                                inj_url = f"https://www.transfermarkt.com.tr/{slug}/sperrenundverletzungen/verein/{team_id}"
                                self._tm_injury_links[team_name] = inj_url
            self._tm_links_fetched = True
        except Exception as e:
            print(f"Failed to fetch TM links: {e}")

    def _norm_name(self, s):
        """Normalize a team name for comparison: strip diacritics, lowercase, remove suffixes."""
        s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('utf-8')
        return s.lower().replace(' sk', '').replace(' jk', '').replace(' fk', '').replace(' a.s.', '').replace(' fc', '').replace(' ', '')

    def _tm_global_search(self, team_name):
        """Search Transfermarkt globally for any team and return its injuries page URL."""
        if team_name in self._tm_injury_links:
            return self._tm_injury_links[team_name]
        
        url = "https://www.transfermarkt.com.tr/schnellsuche/ergebnis/schnellsuche"
        params = {"query": team_name, "x": 0, "y": 0}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9",
        }
        
        try:
            r = self.session.get(url, params=params, headers=headers, timeout=10)
            if r.status_code != 200:
                return None
            
            soup = BeautifulSoup(r.text, 'html.parser')
            candidates = []
            tables = soup.find_all('table', class_='items')
            for table in tables:
                for row in table.find_all('tr'):
                    link = row.find('a', href=True)
                    if link and '/verein/' in link.get('href', ''):
                        href = link['href']
                        display = link.text.strip()
                        parts = href.split('/')
                        try:
                            v_idx = parts.index('verein')
                            verein_id = parts[v_idx + 1]
                            slug = parts[1] if len(parts) > 1 else ''
                            inj_url = f"https://www.transfermarkt.com.tr/{slug}/sperrenundverletzungen/verein/{verein_id}"
                            candidates.append((display, inj_url))
                        except:
                            pass
            
            if not candidates:
                return None
            
            # Score candidates by similarity
            search_n = self._norm_name(team_name)
            best_url = None
            best_score = -1
            
            for display, inj_url in candidates:
                dn = self._norm_name(display)
                if dn == search_n:
                    self._tm_injury_links[team_name] = inj_url
                    return inj_url
                
                score = 0
                if search_n in dn:
                    score = len(search_n) / max(len(dn), 1) * 100
                elif dn in search_n:
                    score = len(dn) / max(len(search_n), 1) * 100
                
                # Bonus for first-word match
                sw = search_n.split() if ' ' in team_name.lower() else [search_n]
                dw = dn.split() if ' ' in display.lower() else [dn]
                if sw and dw and sw[0] == dw[0]:
                    score += 50
                
                if score > best_score:
                    best_score = score
                    best_url = inj_url
            
            if best_url and best_score > 20:
                self._tm_injury_links[team_name] = best_url
                return best_url
            
            # Fallback: first result
            self._tm_injury_links[team_name] = candidates[0][1]
            return candidates[0][1]
        except Exception as e:
            print(f"TM global search error for {team_name}: {e}")
            return None

    def get_transfermarkt_injuries(self, team_name):
        """Web scrapes injuries from Transfermarkt. First checks Super Lig cache, then global search."""
        self._fetch_tm_links()
        
        # Step 1: Try Super Lig cache
        best_match_url = None
        team_n = self._norm_name(team_name)
        for tm_name, url in self._tm_injury_links.items():
            tm_n = self._norm_name(tm_name)
            if tm_n in team_n or team_n in tm_n:
                best_match_url = url
                break
        
        # Step 2: Global search fallback
        if not best_match_url:
            best_match_url = self._tm_global_search(team_name)
        
        if not best_match_url:
            print(f"TM: Could not find team '{team_name}'")
            return []

        # Step 3: Fetch the injuries page
        injured_players = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9",
        }
        try:
            r = self.session.get(best_match_url, headers=headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                tables = soup.find_all('table', class_='items')
                if tables:
                    for td in tables[0].find_all('td', class_='hauptlink'):
                        a_tag = td.find('a')
                        if a_tag and '/profil/spieler/' in a_tag.get('href', ''):
                            p_name = a_tag.text.strip()
                            if p_name and p_name not in injured_players:
                                injured_players.append(p_name)
        except Exception as e:
            print(f"Exception fetching TM injuries for {team_name}: {e}")
            
        return injured_players

    def _get_team_current_league_and_season(self, team_id):
        """Finds the team's actual current domestic league ID and the current season year."""
        if team_id is None:
            return None, None
        
        if team_id in self._team_league_season_cache:
            return self._team_league_season_cache[team_id]

        try:
            r = self.session.get(
                f"{API_FOOTBALL_URL}/leagues",
                headers=self.api_headers,
                params={"team": team_id, "type": "League", "current": "true"},
                timeout=7
            )
            if r.status_code == 200:
                leagues = r.json().get('response', [])
                if leagues:
                    league = leagues[0]
                    league_id = league['league']['id']
                    
                    season_year = None
                    for s in league.get('seasons', []):
                        if s.get('current'):
                            season_year = s.get('year')
                            break
                    
                    # Fallback to the last listed season if none explicitly marked current
                    if not season_year and league.get('seasons'):
                        season_year = league['seasons'][-1]['year']
                    
                    self._team_league_season_cache[team_id] = (league_id, str(season_year) if season_year else None)
                    return league_id, self._team_league_season_cache[team_id][1]
            else:
                print(f"API Error ({r.status_code}) fetching leagues for {team_id}.")
        except Exception as e:
            print(f"Exception fetching leagues for {team_id}: {e}")
            
        return None, None

    def _get_team_api_stats(self, team_id, season, league_id=None):
        """
        Returns real-time form, avg goals from API-Football for a specific season.
        """
        if team_id is None or not season:
            return None
        
        leagues_to_try = [league_id, None] if league_id else [None]
        for lid in leagues_to_try:
            try:
                params = {"team": team_id, "season": season}
                if lid:
                    params["league"] = lid
                r = self.session.get(
                    f"{API_FOOTBALL_URL}/teams/statistics",
                    headers=self.api_headers,
                    params=params,
                    timeout=7
                )
                if r.status_code == 200:
                    json_data = r.json()
                    
                    # Detect if API Plan restricts this season
                    errors = json_data.get('errors', {})
                    if isinstance(errors, dict) and 'plan' in errors:
                        return "PLAN_ERROR"
                        
                    stats = json_data.get('response', {})
                    if stats:
                        return stats
                else:
                    print(f"API Error ({r.status_code}) fetching stats for {team_id} (league {lid}): {r.text}")
            except Exception as e:
                print(f"Exception fetching api stats for {team_id}: {e}")
        return None


    def _normalize_team_name(self, name):
        """
        Normalizes team names to improve match rates with ClubElo.
        Removes common prefixes/suffixes that iddaa uses but ClubElo doesn't.
        """
        name = str(name).strip()
        # Common prefixes to remove
        prefixes = ['RC ', 'FC ', 'AS ', 'AC ', 'US ', 'SSC ', 'AFC ', 'FK ', 'SC ']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
        # Common suffixes
        suffixes = [' FC', ' FK', ' A.S.', ' SC']
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        # Special manual mappings for iddaa -> ClubElo
        mappings = {
            'Bilbao': 'Athletic',
            'Paris St Germain': 'PSG',
            'Bayern Munich': 'Bayern',
            'Real Betis': 'Betis',
            'Real Sociedad': 'Sociedad',
            'AS Roma': 'Roma',
            'Roma': 'Roma',
            'Inter': 'Internazionale',
            'Juventus': 'Juventus'
        }
        name = mappings.get(name, name)
        # ClubElo expects spaces removed
        return name.replace(" ", "")

    def get_team_stats(self, team_name):
        """
        Retrieves enriched team stats from:
        1. API-Football (form, goals, injuries) — PRIMARY
        2. ClubElo API (Elo rating for baseline) — FALLBACK
        
        Returns a dictionary with all features the predictor needs.
        """
        if team_name in self._stats_cache:
            return self._stats_cache[team_name]

        # ──────────────────────────────────────────
        # 1. ClubElo fallback baseline
        # ──────────────────────────────────────────
        elo_score = None
        try:
            formatted_name = self._normalize_team_name(team_name)
            url = f"http://api.clubelo.com/{formatted_name}"
            # ClubElo can sometimes be slow, increasing timeout to 10s
            r = self.session.get(url, timeout=10)
            if r.status_code == 200 and r.text.strip():
                df = pd.read_csv(io.StringIO(r.text))
                if not df.empty and 'Elo' in df.columns:
                    elo_score = float(df.iloc[-1]['Elo'])
        except Exception:
            pass

        # Elo → baseline goals (if available)
        if elo_score is not None:
            avg_scored_base = max(0.5, 1.0 + (elo_score - 1300) / 300.0)
            avg_conceded_base = max(0.5, 2.0 - (elo_score - 1300) / 400.0)
        else:
            avg_scored_base = 1.5
            avg_conceded_base = 1.5

        # ──────────────────────────────────────────
        # 2. API-Football enrichment
        # ──────────────────────────────────────────
        team_id = self._get_team_id(team_name)
        
        # Determine actual current league and season dynamically
        league_id, team_season = self._get_team_current_league_and_season(team_id)
        
        # Fallback if season could not be determined
        if not team_season:
            from datetime import datetime
            now = datetime.now()
            team_season = str(now.year - 1) if now.month < 7 else str(now.year)
            
        # Real goals from API-Football stats
        avg_scored = avg_scored_base
        avg_conceded = avg_conceded_base
        form_score = 0.5       # 0.0 (terrible) to 1.0 (perfect)
        injury_count = 0
        momentum = 0.0         # positive = winning streak, negative = losing streak

        api_stats = None
        # Handle free tier plan limits automatically by stepping back season years if needed
        for _ in range(3):
            api_stats = self._get_team_api_stats(team_id, season=team_season, league_id=league_id)
            if api_stats == "PLAN_ERROR":
                team_season = str(int(team_season) - 1)
                api_stats = None
            else:
                break

        if api_stats:
            goals_for = api_stats.get('goals', {}).get('for', {}).get('average', {})
            goals_against = api_stats.get('goals', {}).get('against', {}).get('average', {})
            
            # 'total' may be null/None; fall back to average of home + away
            gf_total = goals_for.get('total')
            ga_total = goals_against.get('total')
            
            # Safe calculation for average goals scored
            if gf_total is not None and str(gf_total).strip() != "":
                avg_scored = float(gf_total)
            else:
                gf_home = goals_for.get('home')
                gf_away = goals_for.get('away')
                if gf_home is not None and gf_away is not None and str(gf_home).strip() != "" and str(gf_away).strip() != "":
                    avg_scored = (float(gf_home) + float(gf_away)) / 2.0
            
            # Safe calculation for average goals conceded
            if ga_total is not None and str(ga_total).strip() != "":
                avg_conceded = float(ga_total)
            else:
                ga_home = goals_against.get('home')
                ga_away = goals_against.get('away')
                if ga_home is not None and ga_away is not None and str(ga_home).strip() != "" and str(ga_away).strip() != "":
                    avg_conceded = (float(ga_home) + float(ga_away)) / 2.0
            
            # Form: Recent W/D/L string → numeric score
            form_str = api_stats.get('form', '') or ''
            recent_form = form_str[-7:]  # Last 7 matches
            if recent_form:
                wins = recent_form.count('W')
                draws = recent_form.count('D')
                losses = recent_form.count('L')
                total = wins + draws + losses
                if total > 0:
                    form_score = (wins * 1.0 + draws * 0.4) / total
                    
                    # Momentum: last 3 results
                    last_3 = recent_form[-3:]
                    if last_3.count('W') == 3:
                        momentum = 0.2   # hot streak
                    elif last_3.count('L') == 3:
                        momentum = -0.2  # cold streak

        # Injuries (Web scrapes from Transfermarkt unconditionally)
        injuries_list = self.get_transfermarkt_injuries(team_name)
        injury_count = len(injuries_list) if isinstance(injuries_list, list) else 0
        
        # Injury penalty: each missing key player reduces expected goals slightly
        injury_factor = max(0.75, 1.0 - injury_count * 0.005)

        result = {
            'avg_goals_scored': round(avg_scored * injury_factor, 2),
            'avg_goals_conceded': round(avg_conceded, 2),
            'form': round(form_score, 2),
            'momentum': round(momentum, 2),
            'injury_count': injury_count,
            'team_id': team_id,
            'elo': round(elo_score, 0) if elo_score is not None else None
        }
        
        self._stats_cache[team_name] = result
        return result

if __name__ == "__main__":
    fetcher = HistoricalDataFetcher()
    for team in ["Galatasaray", "Fenerbahce", "Real Madrid", "Manchester City"]:
        stats = fetcher.get_team_stats(team)
        print(f"\n{team}: {stats}")
