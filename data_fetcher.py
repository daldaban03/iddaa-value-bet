import pandas as pd
import requests
import io
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime


class HistoricalDataFetcher:
    """
    Data fetcher using FREE data sources only:
    - ClubElo API → Elo ratings
    - football-data.co.uk → match results, form, goals, H2H
    - Transfermarkt → injuries
    """

    LEAGUE_CODES = {
        'T1': 'Süper Lig', 'E0': 'Premier League', 'E1': 'Championship',
        'SP1': 'La Liga', 'SP2': 'La Liga 2',
        'I1': 'Serie A', 'I2': 'Serie B',
        'D1': 'Bundesliga', 'D2': '2. Bundesliga',
        'F1': 'Ligue 1', 'F2': 'Ligue 2',
        'N1': 'Eredivisie', 'B1': 'Jupiler League',
        'P1': 'Liga Portugal', 'G1': 'Super League Greece',
        'SC0': 'Scottish Premiership',
    }

    TRAINING_LEAGUES = ['E0', 'SP1', 'I1', 'D1', 'F1']
    TRAINING_SEASONS = ['2122', '2223', '2324', '2425']

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        self._stats_cache = {}
        self._league_data = {}          # "code_season" -> DataFrame
        self._team_league_map = {}      # norm_name -> (code, canonical)
        self._league_averages = {}
        self._leagues_loaded = False

        # Transfermarkt
        self._tm_injury_links = {}
        self._tm_links_fetched = False

        # Current season
        now = datetime.now()
        if now.month >= 7:
            self._current_season = f"{str(now.year)[2:]}{str(now.year + 1)[2:]}"
        else:
            self._current_season = f"{str(now.year - 1)[2:]}{str(now.year)[2:]}"

    # ═══════════════════════════════════════════════
    # Name normalization
    # ═══════════════════════════════════════════════

    def _norm_name(self, s):
        s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('utf-8')
        s = s.lower().strip()
        for suf in [' sk', ' jk', ' fk', ' a.s.', ' fc', ' sc', ' cf', ' afc']:
            s = s.replace(suf, '')
        return s.replace(' ', '')

    def _normalize_team_name_elo(self, name):
        name = str(name).strip()
        for pre in ['RC ', 'FC ', 'AS ', 'AC ', 'US ', 'SSC ', 'AFC ', 'FK ', 'SC ']:
            if name.startswith(pre):
                name = name[len(pre):]
        for suf in [' FC', ' FK', ' A.S.', ' SC']:
            if name.endswith(suf):
                name = name[:-len(suf)]
        mappings = {
            'Bilbao': 'Athletic', 'Paris St Germain': 'PSG',
            'Bayern Munich': 'Bayern', 'Real Betis': 'Betis',
            'Real Sociedad': 'Sociedad', 'AS Roma': 'Roma',
            'Roma': 'Roma', 'Inter': 'Internazionale',
        }
        return mappings.get(name, name).replace(" ", "")

    # ═══════════════════════════════════════════════
    # ClubElo API (FREE)
    # ═══════════════════════════════════════════════

    def _get_elo(self, team_name):
        try:
            formatted = self._normalize_team_name_elo(team_name)
            r = self.session.get(f"http://api.clubelo.com/{formatted}", timeout=10)
            if r.status_code == 200 and r.text.strip():
                df = pd.read_csv(io.StringIO(r.text))
                if not df.empty and 'Elo' in df.columns:
                    return float(df.iloc[-1]['Elo'])
        except Exception:
            pass
        return None

    # ═══════════════════════════════════════════════
    # football-data.co.uk CSV (FREE)
    # ═══════════════════════════════════════════════

    def _fetch_league_csv(self, league_code, season=None):
        if season is None:
            season = self._current_season

        cache_key = f"{league_code}_{season}"
        if cache_key in self._league_data:
            return self._league_data[cache_key]

        target_url = f"https://www.football-data.co.uk/mmz4281/{season}/{league_code}.csv"
        
        # Denenecek URL rotaları (Türkiye'deki erişim engellerini veya timeout'ları aşmak için ayna siteler)
        urls_to_try = [
            f"https://corsproxy.io/?url={target_url}",
            f"https://api.allorigins.win/raw?url={target_url}",
            target_url
        ]
        
        for url in urls_to_try:
            try:
                r = self.session.get(url, timeout=15)
                if r.status_code == 200 and r.text.strip():
                    df = pd.read_csv(io.StringIO(r.text), on_bad_lines='skip')
                    if 'HomeTeam' in df.columns and 'AwayTeam' in df.columns:
                        if 'Date' in df.columns:
                            df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
                            df = df.sort_values('Date').reset_index(drop=True)

                        self._league_data[cache_key] = df
                        for team in set(df['HomeTeam'].dropna()) | set(df['AwayTeam'].dropna()):
                            norm = self._norm_name(str(team))
                            self._team_league_map[norm] = (league_code, str(team))
                        return df
            except Exception as e:
                print(f"  CSV fetch failed ({league_code}/{season}) via {url}: {e}")
        
        return None

    def _ensure_leagues_loaded(self):
        if self._leagues_loaded:
            return
        print("Lig verileri football-data.co.uk'dan çekiliyor...")
        for code in self.LEAGUE_CODES:
            df = self._fetch_league_csv(code)
            if df is not None:
                print(f"  ✓ {self.LEAGUE_CODES[code]}: {len(df)} maç")
        self._leagues_loaded = True

    def _find_team_in_leagues(self, team_name):
        """Returns (league_code, canonical_name, league_df) or (None, None, None)."""
        self._ensure_leagues_loaded()

        norm = self._norm_name(team_name)

        if norm in self._team_league_map:
            code, canonical = self._team_league_map[norm]
            df = self._league_data.get(f"{code}_{self._current_season}")
            if df is not None:
                return code, canonical, df

        best_match, best_score = None, 0
        for cached_norm, (code, canonical) in self._team_league_map.items():
            score = 0
            if norm == cached_norm:
                score = 100
            elif norm in cached_norm:
                score = len(norm) / max(len(cached_norm), 1) * 80
            elif cached_norm in norm:
                score = len(cached_norm) / max(len(norm), 1) * 80
            if score > best_score:
                best_score = score
                best_match = (code, canonical)

        if best_match and best_score > 40:
            self._team_league_map[norm] = best_match
            code, canonical = best_match
            df = self._league_data.get(f"{code}_{self._current_season}")
            return code, canonical, df

        return None, None, None

    def _get_league_averages(self, league_code):
        if league_code in self._league_averages:
            return self._league_averages[league_code]

        df = self._league_data.get(f"{league_code}_{self._current_season}")
        if df is not None and 'FTHG' in df.columns:
            avg_home = float(df['FTHG'].dropna().mean())
            avg_away = float(df['FTAG'].dropna().mean())
        else:
            avg_home, avg_away = 1.5, 1.15

        result = {'avg_home_goals': round(avg_home, 3), 'avg_away_goals': round(avg_away, 3)}
        self._league_averages[league_code] = result
        return result

    def _compute_team_csv_stats(self, canonical_name, league_df):
        """Compute home/away goal averages, form, momentum from CSV."""
        home_m = league_df[league_df['HomeTeam'] == canonical_name]
        away_m = league_df[league_df['AwayTeam'] == canonical_name]

        h_scored = float(home_m['FTHG'].mean()) if (not home_m.empty and 'FTHG' in home_m.columns) else 1.4
        h_conced = float(home_m['FTAG'].mean()) if (not home_m.empty and 'FTAG' in home_m.columns) else 1.1
        a_scored = float(away_m['FTAG'].mean()) if (not away_m.empty and 'FTAG' in away_m.columns) else 1.0
        a_conced = float(away_m['FTHG'].mean()) if (not away_m.empty and 'FTHG' in away_m.columns) else 1.5

        # Form: combine home+away, sort by date
        results = []
        for _, row in home_m.iterrows():
            ftr = row.get('FTR', '')
            d = row.get('Date', pd.NaT)
            res_val = 1 if ftr == 'H' else (0 if ftr == 'D' else -1 if ftr == 'A' else None)
            if res_val is not None:
                results.append((d, res_val))

        for _, row in away_m.iterrows():
            ftr = row.get('FTR', '')
            d = row.get('Date', pd.NaT)
            res_val = 1 if ftr == 'A' else (0 if ftr == 'D' else -1 if ftr == 'H' else None)
            if res_val is not None:
                results.append((d, res_val))

        results.sort(key=lambda x: x[0] if pd.notna(x[0]) else pd.Timestamp.min)
        result_vals = [r[1] for r in results]

        # Form (last 7)
        last7 = result_vals[-7:] if len(result_vals) >= 7 else result_vals
        form_score = 0.5
        if last7:
            form_score = (sum(1 for r in last7 if r == 1) + sum(0.4 for r in last7 if r == 0)) / len(last7)

        # Momentum (last 3)
        momentum = 0.0
        if len(result_vals) >= 3:
            last3 = result_vals[-3:]
            if all(r == 1 for r in last3):
                momentum = 0.2
            elif all(r == -1 for r in last3):
                momentum = -0.2

        return {
            'home_goals_scored': round(h_scored, 3),
            'home_goals_conceded': round(h_conced, 3),
            'away_goals_scored': round(a_scored, 3),
            'away_goals_conceded': round(a_conced, 3),
            'avg_goals_scored': round((h_scored + a_scored) / 2, 3),
            'avg_goals_conceded': round((h_conced + a_conced) / 2, 3),
            'form': round(form_score, 2),
            'momentum': round(momentum, 2),
        }

    # ═══════════════════════════════════════════════
    # H2H from football-data.co.uk
    # ═══════════════════════════════════════════════

    def get_h2h(self, home_team, away_team):
        """H2H record from CSV data (current + past 3 seasons)."""
        _, home_c, _ = self._find_team_in_leagues(home_team)
        _, away_c, _ = self._find_team_in_leagues(away_team)
        if not home_c or not away_c:
            return {'total': 0}

        code, _, _ = self._find_team_in_leagues(home_team)
        h2h_results = []

        seasons_to_check = [self._current_season] + ['2324', '2223', '2122']
        for season in seasons_to_check:
            ck = f"{code}_{season}"
            if ck not in self._league_data:
                self._fetch_league_csv(code, season)
            df = self._league_data.get(ck)
            if df is None:
                continue

            mask1 = (df['HomeTeam'] == home_c) & (df['AwayTeam'] == away_c)
            mask2 = (df['HomeTeam'] == away_c) & (df['AwayTeam'] == home_c)
            for _, row in df[mask1 | mask2].iterrows():
                ftr = row.get('FTR', '')
                ht = row.get('HomeTeam', '')
                if ht == home_c:
                    h2h_results.append(1 if ftr == 'H' else (0 if ftr == 'D' else -1))
                else:
                    h2h_results.append(1 if ftr == 'A' else (0 if ftr == 'D' else -1))

        total = len(h2h_results)
        if total == 0:
            return {'total': 0}

        hw = sum(1 for r in h2h_results if r == 1)
        dr = sum(1 for r in h2h_results if r == 0)
        aw = sum(1 for r in h2h_results if r == -1)

        return {
            'total': total,
            'home_wins': hw,
            'draws': dr,
            'away_wins': aw,
            'home_dominance': round((hw - aw) / total, 2),
        }

    # ═══════════════════════════════════════════════
    # Transfermarkt injuries (keep existing)
    # ═══════════════════════════════════════════════

    def _fetch_tm_links(self):
        if self._tm_links_fetched:
            return
        url = "https://www.transfermarkt.com.tr/super-lig/startseite/wettbewerb/TR1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
            print(f"TM links fetch failed: {e}")

    def _tm_global_search(self, team_name):
        if team_name in self._tm_injury_links:
            return self._tm_injury_links[team_name]

        url = "https://www.transfermarkt.com.tr/schnellsuche/ergebnis/schnellsuche"
        params = {"query": team_name, "x": 0, "y": 0}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9",
        }
        try:
            r = self.session.get(url, params=params, headers=headers, timeout=10)
            if r.status_code != 200:
                return None

            soup = BeautifulSoup(r.text, 'html.parser')
            candidates = []
            for table in soup.find_all('table', class_='items'):
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

            search_n = self._norm_name(team_name)
            best_url, best_score = None, -1

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

                if score > best_score:
                    best_score = score
                    best_url = inj_url

            if best_url and best_score > 20:
                self._tm_injury_links[team_name] = best_url
                return best_url

            self._tm_injury_links[team_name] = candidates[0][1]
            return candidates[0][1]
        except Exception as e:
            print(f"TM global search error for {team_name}: {e}")
            return None

    def get_transfermarkt_injuries(self, team_name):
        self._fetch_tm_links()

        best_match_url = None
        team_n = self._norm_name(team_name)
        for tm_name, url in self._tm_injury_links.items():
            if self._norm_name(tm_name) in team_n or team_n in self._norm_name(tm_name):
                best_match_url = url
                break

        if not best_match_url:
            best_match_url = self._tm_global_search(team_name)

        if not best_match_url:
            return []

        injured_players = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9",
        }
        try:
            r = self.session.get(best_match_url, headers=headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                tables = soup.find_all('table', class_='items')
                if tables:
                    rows = tables[0].find_all('tr', class_=['odd', 'even'])
                    for row in rows:
                        name_td = row.find('td', class_='hauptlink')
                        if not name_td: continue
                        
                        a_tag = name_td.find('a')
                        if not (a_tag and '/profil/spieler/' in a_tag.get('href', '')):
                            continue
                            
                        p_name = a_tag.text.strip()
                        if p_name and not any(p.get('name') == p_name for p in injured_players):
                            tds = row.find_all('td')
                            val_str = ""
                            if len(tds) > 0:
                                val_str = tds[-1].text.strip()
                            
                            value_m = self._parse_market_value(val_str)
                            injured_players.append({
                                'name': p_name,
                                'val_str': val_str,
                                'value_m': value_m
                            })
        except Exception as e:
            print(f"TM injuries error for {team_name}: {e}")

        return injured_players

    def _parse_market_value(self, val_str):
        """Converts strings like '15.00m €' or '500k €' to float millions (e.g., 15.0 or 0.50)."""
        val_str = val_str.lower().replace('€', '').strip()
        if not val_str or val_str == '-':
            return 0.0
        try:
            if 'm' in val_str:
                return float(val_str.replace('m', '').strip())
            elif 'k' in val_str:
                return float(val_str.replace('k', '').strip()) / 1000.0
            else:
                return float(val_str)
        except:
            return 0.0

    # ═══════════════════════════════════════════════
    # Training Data for ML Model
    # ═══════════════════════════════════════════════

    def get_training_data(self):
        """
        Build training dataset from football-data.co.uk historical CSVs.
        Uses rolling stats to prevent data leakage.
        Returns (X, y) numpy-compatible lists.
        """
        import numpy as np
        print("Eğitim verisi oluşturuluyor (5 lig × 4 sezon)...")
        X, y = [], []

        for league in self.TRAINING_LEAGUES:
            for season in self.TRAINING_SEASONS:
                df = self._fetch_league_csv(league, season)
                if df is None or df.empty:
                    continue

                # Rolling stats per team
                t_home_goals = {}
                t_home_conc = {}
                t_away_goals = {}
                t_away_conc = {}
                t_results = {}

                for _, row in df.iterrows():
                    home = row.get('HomeTeam')
                    away = row.get('AwayTeam')
                    fthg = row.get('FTHG')
                    ftag = row.get('FTAG')
                    ftr = row.get('FTR')

                    if pd.isna(home) or pd.isna(away) or pd.isna(fthg) or pd.isna(ftag) or pd.isna(ftr):
                        continue

                    fthg, ftag = float(fthg), float(ftag)

                    # Current stats (BEFORE this match)
                    h_hg = t_home_goals.get(home, [])
                    h_hc = t_home_conc.get(home, [])
                    a_ag = t_away_goals.get(away, [])
                    a_ac = t_away_conc.get(away, [])
                    h_res = t_results.get(home, [])
                    a_res = t_results.get(away, [])

                    # Need minimum 3 matches per team
                    if len(h_res) >= 3 and len(a_res) >= 3:
                        h_scored_avg = float(np.mean(h_hg[-10:])) if h_hg else 1.4
                        h_conced_avg = float(np.mean(h_hc[-10:])) if h_hc else 1.1
                        a_scored_avg = float(np.mean(a_ag[-10:])) if a_ag else 1.0
                        a_conced_avg = float(np.mean(a_ac[-10:])) if a_ac else 1.5

                        h_form = self._form_score(h_res)
                        a_form = self._form_score(a_res)
                        h_mom = self._momentum(h_res)
                        a_mom = self._momentum(a_res)

                        X.append([
                            h_scored_avg, h_conced_avg,
                            a_scored_avg, a_conced_avg,
                            h_scored_avg - a_scored_avg,
                            h_form, a_form,
                            h_mom, a_mom
                        ])

                        label = 1 if ftr == 'H' else (0 if ftr == 'D' else 2)
                        y.append(label)

                    # Update rolling stats
                    t_home_goals.setdefault(home, []).append(fthg)
                    t_home_goals[home] = t_home_goals[home][-10:]
                    t_home_conc.setdefault(home, []).append(ftag)
                    t_home_conc[home] = t_home_conc[home][-10:]
                    t_away_goals.setdefault(away, []).append(ftag)
                    t_away_goals[away] = t_away_goals[away][-10:]
                    t_away_conc.setdefault(away, []).append(fthg)
                    t_away_conc[away] = t_away_conc[away][-10:]

                    h_r = 1 if fthg > ftag else (0 if fthg == ftag else -1)
                    a_r = 1 if ftag > fthg else (0 if fthg == ftag else -1)
                    t_results.setdefault(home, []).append(h_r)
                    t_results[home] = t_results[home][-10:]
                    t_results.setdefault(away, []).append(a_r)
                    t_results[away] = t_results[away][-10:]

                print(f"  ✓ {self.LEAGUE_CODES.get(league, league)} {season}: toplam {len(X)} örnek")

        print(f"Eğitim verisi hazır: {len(X)} maç, 9 özellik")
        return X, y

    @staticmethod
    def _form_score(result_list):
        if not result_list:
            return 0.5
        last7 = result_list[-7:]
        return (sum(1 for r in last7 if r == 1) + sum(0.4 for r in last7 if r == 0)) / len(last7)

    @staticmethod
    def _momentum(result_list):
        if len(result_list) < 3:
            return 0.0
        last3 = result_list[-3:]
        if all(r == 1 for r in last3):
            return 0.2
        if all(r == -1 for r in last3):
            return -0.2
        return 0.0

    # ═══════════════════════════════════════════════
    # Main Interface
    # ═══════════════════════════════════════════════

    def get_team_stats(self, team_name):
        if team_name in self._stats_cache:
            return self._stats_cache[team_name]

        # 1. ClubElo
        elo_score = self._get_elo(team_name)

        # 2. football-data.co.uk stats
        code, canonical, league_df = self._find_team_in_leagues(team_name)

        if code and canonical and league_df is not None:
            csv_stats = self._compute_team_csv_stats(canonical, league_df)
            league_avg = self._get_league_averages(code)
        else:
            # Fallback: Elo-based estimation
            if elo_score is not None:
                avg_s = max(0.5, 1.0 + (elo_score - 1300) / 300.0)
                avg_c = max(0.5, 2.0 - (elo_score - 1300) / 400.0)
            else:
                avg_s, avg_c = 1.5, 1.5

            csv_stats = {
                'home_goals_scored': round(avg_s * 1.1, 3),
                'home_goals_conceded': round(avg_c * 0.9, 3),
                'away_goals_scored': round(avg_s * 0.85, 3),
                'away_goals_conceded': round(avg_c * 1.15, 3),
                'avg_goals_scored': round(avg_s, 3),
                'avg_goals_conceded': round(avg_c, 3),
                'form': 0.5,
                'momentum': 0.0,
            }
            league_avg = {'avg_home_goals': 1.5, 'avg_away_goals': 1.15}

        # 3. Injuries from Transfermarkt
        injuries = self.get_transfermarkt_injuries(team_name)
        injury_count = len(injuries) if isinstance(injuries, list) else 0

        result = {
            **csv_stats,
            'injury_count': injury_count,
            'elo': round(elo_score, 0) if elo_score is not None else None,
            'league_avg_home_goals': league_avg['avg_home_goals'],
            'league_avg_away_goals': league_avg['avg_away_goals'],
        }

        self._stats_cache[team_name] = result
        return result


if __name__ == "__main__":
    fetcher = HistoricalDataFetcher()
    for team in ["Galatasaray", "Fenerbahce", "Real Madrid", "Manchester City"]:
        stats = fetcher.get_team_stats(team)
        print(f"\n{team}: {stats}")
