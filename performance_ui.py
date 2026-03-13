import streamlit as st
import pandas as pd
import glob
import json
import os
from datetime import datetime

PREDICTIONS_DIR = "data/predictions"

def verify_results(predictions, fetcher):
    """
    Result verification using HistoricalDataFetcher.
    """
    verified_results = []
    correct_count = 0
    total_verified = 0
    
    for pred in predictions:
        match_name = pred['Match']
        home, away = match_name.split(' vs ')
        
        # Search for teams in league data
        l_code, h_canon, _ = fetcher._find_team_in_leagues(home)
        _, a_canon, df = fetcher._find_team_in_leagues(away)
        
        status = "Bekleniyor"
        is_won = None
        
        if h_canon and a_canon and df is not None:
            # Look for this specific fixture in history
            mask = (df['HomeTeam'] == h_canon) & (df['AwayTeam'] == a_canon)
            match_row = df[mask]
            
            if not match_row.empty:
                fthg = match_row.iloc[0].get('FTHG')
                ftag = match_row.iloc[0].get('FTAG')
                ftr = match_row.iloc[0].get('FTR')
                
                if pd.notna(ftr):
                    total_verified += 1
                    status = f"{int(fthg)}-{int(ftag)} ({ftr})"
                    
                    # Check if our prediction won
                    # Prediction format: "1 (Ev Sahibi)", "X (Beraberlik)", "2 (Deplasman)"
                    pred_type = pred['Prediction'].split(' ')[0]
                    if (pred_type == '1' and ftr == 'H') or \
                       (pred_type == 'X' and ftr == 'D') or \
                       (pred_type == '2' and ftr == 'A'):
                        is_won = True
                        correct_count += 1
                    else:
                        is_won = False

        status_icon = "✅ Kazandı" if is_won is True else ("❌ Kaybetti" if is_won is False else "⏳ Beklemede")
        
        verified_results.append({
            "Match": match_name,
            "Prediction": pred['Prediction'],
            "Result": status,
            "Status": status_icon
        })
    
    return verified_results, correct_count, total_verified

def render_performance_tab(fetcher):
    st.header("📈 Performans Analizi")
    
    files = glob.glob(os.path.join(PREDICTIONS_DIR, "*.json"))
    if not files:
        st.info("Henüz kaydedilmiş bir tahmin geçmişi bulunmuyor.")
        return

    all_data = []
    for f in files:
        with open(f, "r", encoding="utf-8") as file:
            all_data.append(json.load(file))
            
    all_data.sort(key=lambda x: x['metadata']['timestamp'], reverse=True)
    
    # Session selection
    selected_session_ts = st.selectbox(
        "Geçmiş Analiz Seçin:",
        options=[d['metadata']['timestamp'] for d in all_data],
        key="session_selector",
        format_func=lambda x: datetime.strptime(x, "%Y%m%d_%H%M%S").strftime("%d %b %Y, %H:%M")
    )
    
    selected_data = next(d for d in all_data if d['metadata']['timestamp'] == selected_session_ts)
    predictions = selected_data['predictions']
    
    st.subheader(f"🔍 Detaylar: {selected_session_ts}")
    
    # Verification
    if st.button("🔄 Sonuçları Kontrol Et", use_container_width=True):
        st.session_state[f'verified_{selected_session_ts}'] = True

    if st.session_state.get(f'verified_{selected_session_ts}', False):
        with st.spinner("Sonuçlar doğrulanıyor..."):
            verified_list, correct, total = verify_results(predictions, fetcher)
            
            # KPIs for the session
            c1, c2, c3 = st.columns(3)
            c1.metric("Doğrulanan Maç", total)
            c2.metric("Doğru Tahmin", correct)
            if total > 0:
                c3.metric("Başarı Oranı", f"%{100*correct/total:.1f}")
            
            st.table(pd.DataFrame(verified_list))
    else:
        # Display table without verification
        display_df = pd.DataFrame(predictions)[['Match', 'Prediction', 'AI_Probability', 'Iddaa_Odds', 'Kelly_Bahis']].copy()
        display_df['Durum'] = "⏳ Beklemede"
        st.table(display_df)

