import streamlit as st
import pandas as pd
import glob
import json
import os
from datetime import datetime
from utils.persistence import PREDICTIONS_DIR, update_prediction_results

def render_performance_tab(fetcher):
    st.header("📈 Performans Analizi")
    
    # 1. Background Result Update Trigger (Optional/Manual)
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🔄 Tüm Sonuçları Güncelle (Derin Tarama)", use_container_width=True):
            with st.spinner("Football-Data.co.uk üzerinden sonuçlar çekiliyor..."):
                # Force refresh search by clearing fetcher's failed urls or just letting it run
                # We'll call update_prediction_results which handles the logic
                updated = update_prediction_results(fetcher)
                st.success(f"{updated} dosya güncellendi!")
                st.rerun()

    # 2. Global Performance Dashboard
    files = glob.glob(os.path.join(PREDICTIONS_DIR, "*.json"))
    if not files:
        st.info("Henüz kaydedilmiş bir tahmin geçmişi bulunmuyor.")
        return

    all_predictions = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                if 'predictions' in data:
                    all_predictions.extend(data['predictions'])
        except:
            continue

    if all_predictions:
        df_all = pd.DataFrame(all_predictions)
        
        # Filter for verified ones
        verified_df = df_all[df_all['Status'].isin(["✅ Kazandı", "❌ Kaybetti"])].copy()
        
        st.subheader("📊 Genel Başarı Özeti")
        k1, k2, k3, k4 = st.columns(4)
        
        total = len(verified_df)
        wins = len(verified_df[verified_df['Status'] == "✅ Kazandı"])
        
        k1.metric("Toplam Bahis", total)
        
        if total > 0:
            win_rate = (wins / total) * 100
            k2.metric("Başarı Oranı", f"%{win_rate:.1f}")
            
            # Profit/Loss Calculation
            # Need to handle TL formatting (e.g. "1,200")
            def parse_money(val_str):
                if pd.isna(val_str): return 0.0
                return float(str(val_str).replace(',', '').replace(' TL', ''))

            verified_df['Bet_Amount'] = verified_df['Kelly_Bahis'].apply(parse_money)
            verified_df['Profit'] = verified_df.apply(
                lambda r: r['Bet_Amount'] * (float(r['Iddaa_Odds']) - 1) if r['Status'] == "✅ Kazandı" else -r['Bet_Amount'],
                axis=1
            )
            
            total_profit = verified_df['Profit'].sum()
            total_staked = verified_df['Bet_Amount'].sum()
            roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
            
            k3.metric("Toplam Kâr/Zarar", f"{total_profit:,.0f} TL", delta=f"{total_profit:,.0f} TL")
            k4.metric("ROI (Yield)", f"%{roi:.1f}")
        else:
            k2.metric("Başarı Oranı", "-")
            k3.metric("Toplam Kâr/Zarar", "-")
            k4.metric("ROI (Yield)", "-")

    st.markdown("---")
    
    # 3. Session Selection and Detailed View
    all_sessions = []
    for f in files:
        with open(f, "r", encoding="utf-8") as file:
            all_sessions.append(json.load(file))
            
    all_sessions.sort(key=lambda x: x['metadata']['timestamp'], reverse=True)
    
    selected_session_ts = st.selectbox(
        "Geçmiş Analiz Seçin:",
        options=[d['metadata']['timestamp'] for d in all_sessions],
        key="session_selector",
        format_func=lambda x: datetime.strptime(x, "%Y%m%d_%H%M%S").strftime("%d %b %Y, %H:%M")
    )
    
    selected_data = next(d for d in all_sessions if d['metadata']['timestamp'] == selected_session_ts)
    predictions = selected_data['predictions']
    
    st.subheader(f"🔍 Detaylar: {selected_session_ts}")
    
    display_df = pd.DataFrame(predictions)
    
    # Selection of columns for display
    cols = ['Match', 'Prediction', 'Iddaa_Odds', 'AI_Probability', 'Kelly_Bahis']
    if 'Result' in display_df.columns:
        cols.append('Result')
    if 'Status' in display_df.columns:
        cols.append('Status')
    else:
        display_df['Status'] = "⏳ Beklemede"
        cols.append('Status')
        
    st.table(display_df[cols])

