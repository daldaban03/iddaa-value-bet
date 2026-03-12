import streamlit as st
import pandas as pd
import glob
import json
import os
from datetime import datetime

PREDICTIONS_DIR = "data/predictions"

def verify_results(predictions, fetcher):
    """
    Very basic result verification using HistoricalDataFetcher.
    Matches team names and checks results for the given date.
    """
    results = []
    correct_count = 0
    total_verified = 0
    
    for pred in predictions:
        match_name = pred['Match']
        home, away = match_name.split(' vs ')
        # Mock logic or actual fetcher lookup would go here
        # For v2.0, we show 'Pending' if not found in recent bulten
        status = "Bilinmiyor"
        is_correct = None
        
        # Simple simulation for demo if not using real API
        # In production, this would call fetcher.get_match_result(home, away)
        results.append({
            "Match": match_name,
            "Prediction": pred['Prediction'],
            "Result": "Bekleniyor",
            "Status": "⏳ Beklemede"
        })
    
    return results, correct_count, total_verified

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
    
    # KPIs
    st.subheader("📊 Sistem Başarısı")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Analiz Sayısı", len(all_data))
    col2.metric("Toplam Tahmin", sum(len(d['predictions']) for d in all_data))
    col3.metric("Başarı Oranı", "%--")
    col4.metric("Net ROI", "%--")
    
    st.markdown("---")
    
    selected_session_ts = st.selectbox(
        "Geçmiş Analiz Seçin:",
        options=[d['metadata']['timestamp'] for d in all_data],
        format_func=lambda x: datetime.strptime(x, "%Y%m%d_%H%M%S").strftime("%d %b %Y, %H:%M")
    )
    
    selected_data = next(d for d in all_data if d['metadata']['timestamp'] == selected_session_ts)
    df_session = pd.DataFrame(selected_data['predictions'])
    
    st.subheader(f"🔍 Detaylar: {selected_session_ts}")
    
    # Action button for live verification
    if st.button("🔄 Sonuçları Kontrol Et", use_container_width=True):
        with st.spinner("Sonuçlar doğrulanıyor..."):
            # This is a placeholder for the actual matching logic
            # which would involve fetcher.scrape_results()
            st.warning("Canlı skor doğrulama özelliği için bültenin sonuçlanması bekleniyor.")
            
    # Display table with icons
    display_df = df_session[['Match', 'Prediction', 'AI_Probability', 'Iddaa_Odds', 'Kelly_Bahis']].copy()
    display_df['Durum'] = "⏳ Beklemede"
    st.table(display_df)

