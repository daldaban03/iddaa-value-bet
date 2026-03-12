import streamlit as st
import pandas as pd
from scraper import IddaaScraper
from data_fetcher import HistoricalDataFetcher
from predictor import Predictor
from analyzer import ValueAnalyzer

st.set_page_config(
    page_title="Iddaa Value Bet AI",
    page_icon="⚽",
    layout="wide"
)

st.title("🎯 Iddaa Value Bet AI Analyzer")
st.markdown("""
Bu araç, seçili maçların **Yapay Zeka** modeli (Elo + Form + Transfermarkt Sakatlık Analizi) ile hesaplanmış kazanma ihtimallerini, 
**iddaa** oranları ile karşılaştırarak matematiksel olarak kârlı **Value Bet (Değerli Bahis)** fırsatlarını tespit eder.
""")

# Initialize modules once and cache them for the entire server session
@st.cache_resource
def load_modules():
    # Cache buster v3: Force reload of classes to fix AttributeError
    scraper = IddaaScraper()
    fetcher = HistoricalDataFetcher()
    predictor = Predictor(fetcher)
    analyzer = ValueAnalyzer(predictor)
    return scraper, fetcher, predictor, analyzer

scraper, fetcher, predictor, analyzer = load_modules()

BANKROLL = 100000

col1, col2 = st.columns([1, 1])

with col1:
    st.header("1. Günlük Bülten")
    if st.button("Bülteni Çek", type="primary"):
        with st.spinner("Bülten indiriliyor..."):
            try:
                # Fetch daily data
                bulten_df = scraper.fetch_daily_bulten()
                
                st.session_state['bulten'] = bulten_df
                st.success(f"{len(bulten_df)} maç başarıyla çekildi.")
            except Exception as e:
                st.error(f"Hata: {e}")

    if 'bulten' in st.session_state:
        st.dataframe(st.session_state['bulten'])

with col2:
    st.header("2. Value Bet Analizi")
    
    # Initialize UI state
    if 'is_analyzing' not in st.session_state:
        st.session_state['is_analyzing'] = False
        
    # Kullanıcıya güvenli marj (Edge) seçtirme şansı verelim
    min_edge_pct = st.slider(
        "Minimum Beklenen Kâr (Edge) Oranı %", 
        min_value=0.0, max_value=30.0, value=5.0, step=1.0,
        disabled=st.session_state['is_analyzing']
    )
    st.caption("Not: Bültendeki oranların şirket kâr marjını yenmesi için en az %5 seçilmesi daha risksizdir (objektif).")

    if 'bulten' in st.session_state:
        if st.button("Yapay Zeka ile Analiz Et", type="primary", disabled=st.session_state['is_analyzing']):
            st.session_state['is_analyzing'] = True
            try:
                with st.spinner("Maç istatistikleri ve sakatlıklar inceleniyor, ihtimaller hesaplanıyor..."):
                    value_bets_df = analyzer.analyze_fixtures(
                        st.session_state['bulten'], 
                        min_edge=min_edge_pct/100.0,
                        bankroll=BANKROLL
                    )
                    st.session_state['value_bets'] = value_bets_df
            except Exception as e:
                st.error(f"Hata oluştu: {e}")
                import traceback
                st.code(traceback.format_exc())
            finally:
                st.session_state['is_analyzing'] = False
                st.rerun() # Refresh UI to enable slider/button again
                    
        if 'value_bets' in st.session_state:
            df = st.session_state['value_bets']
            if not df.empty:
                st.success(f"**{len(df)}** adet Value Bet (Değerli Bahis) bulundu!")
                
                # Ana tablo: Explanation ve Expected_Value gizle, eksik ve kelly göster
                display_cols = ['Date', 'Match', 'Veri_Kalitesi', 'Prediction', 'AI_Probability', 'Iddaa_Odds', 
                               'Edge', 'Ev_Eksik', 'Dep_Eksik', 'Kelly_Pct', 'Kelly_Bahis']
                available_cols = [c for c in display_cols if c in df.columns]
                st.dataframe(df[available_cols], use_container_width=True)
                
                # Kullanıcı AI Düşünce panelini görsün
                if 'Explanation' in df.columns:
                    with st.expander("🤖 Yapay Zeka Nasıl Düşündü? (Tıklayıp İnceleyin)"):
                        st.write("Aşağıda bulduğumuz en değerli bahis ihtimallerinin arkasındaki yapay zeka matematiğini görebilirsiniz:")
                        for idx, row in df.head(5).iterrows():
                            st.markdown(f"**{row['Match']} - Tahmin: {row['Prediction']}**")
                            st.info(row['Explanation'])

                # Plot the edge chart
                st.subheader("Avantaj (Edge) Grafiği")
                chart_data = df[['Match', 'Edge']].copy()
                chart_data['Edge'] = chart_data['Edge'].str.rstrip('%').astype(float)
                st.bar_chart(chart_data.set_index('Match'))
            else:
                st.warning("Bugünkü bültende belirlediğiniz marjın üzerinde değerli (Value Bet) bahis bulunamadı. Lütfen daha sonra tekrar deneyin veya Edge oranını düşürün.")
    else:
        st.info("Analiz için önce bülteni çekiniz.")

# ── Kupon Oluşturucu Paneli ───────────────────────────────────────
st.markdown("---")
st.header("3. 🎫 Önerilen Kupon (Kelly Kriteri)")

if 'value_bets' in st.session_state and not st.session_state['value_bets'].empty:
    df = st.session_state['value_bets']
    
    singles, system_coupon, total_stake = analyzer.build_coupon(df, bankroll=BANKROLL)
    
    if singles:
        st.subheader("📌 Tekli Bahisler (Düşük Risk)")
        st.markdown(f"**Sermaye:** {BANKROLL:,.0f} TL | **Risk İştahı:** Yüksek (Half-Kelly)")
        
        for i, bet in enumerate(singles, 1):
            with st.container():
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                with c1:
                    st.markdown(f"**{i}. {bet['match']}**")
                    st.caption(f"Tahmin: {bet['prediction']} | AI: {bet['ai_prob']} | Edge: {bet['edge']}")
                    st.caption(f"🏥 Ev Eksik: {bet['ev_eksik']} | Dep Eksik: {bet['dep_eksik']}")
                with c2:
                    st.metric("Oran", f"{bet['odds']:.2f}")
                with c3:
                    st.metric("Kelly", bet['kelly_pct'])
                with c4:
                    st.metric("Bahis", f"{bet['kelly_bet']} TL")
        
        st.markdown(f"**Toplam Tekli Bahis Yatırımı:** {total_stake:,.0f} TL ({total_stake/BANKROLL*100:.1f}% sermaye)")
    
    if system_coupon:
        st.markdown("---")
        st.subheader("🔗 Sistem Kuponu (Yüksek Getiri)")
        
        st.markdown(f"**Kupon Tipi:** {system_coupon['type']}")
        
        legs_text = ""
        for leg in system_coupon['legs']:
            legs_text += f"- **{leg['match']}** → {leg['prediction']} (Oran: {leg['odds']:.2f}, AI: {leg['ai_prob']})\n"
        st.markdown(legs_text)
        
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.metric("Kombine Oran", f"{system_coupon['combined_odds']:.2f}")
        with r2:
            st.metric("Kombine Olasılık", system_coupon['combined_prob'])
        with r3:
            st.metric("Yatırım", system_coupon['formatted_stake'])
        with r4:
            st.metric("Potansiyel Kazanç", f"{system_coupon['potential_win']:,.0f} TL")
        
        st.caption(f"Sistem EV (Beklenen Kâr): {system_coupon['system_ev']}")
    
    if not singles and not system_coupon:
        st.info("Kupon oluşturmak için yeterli Value Bet bulunamadı.")
else:
    st.info("Kupon oluşturmak için önce Value Bet analizi yapınız.")

st.markdown("---")
st.caption("🚨 Uyarı: Bu sadece matematiksel tahmin ve olasılıkları analiz eden eğitsel bir araçtır. %100 kesinlik garanti etmez.")
