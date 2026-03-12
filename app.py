import streamlit as st
import pandas as pd
from scraper import IddaaScraper
from data_fetcher import HistoricalDataFetcher
from predictor import Predictor
from analyzer import ValueAnalyzer
from utils.persistence import save_predictions
from performance_ui import render_performance_tab
from utils.background_worker import BackgroundAnalyzer, get_latest_scan

# 🕒 Start Background Automation
@st.cache_resource
def start_automation():
    worker = BackgroundAnalyzer(interval_seconds=900)  # 15 mins
    if not worker.is_alive():
        worker.start()
    return worker

worker = start_automation()

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

# ⚙️ Sidebar Settings
with st.sidebar:
    st.header("⚙️ Ayarlar")
    BANKROLL = st.number_input("Sermaye (TL)", value=100000, step=1000)
    # Default risk fraction (half-Kelly is 0.5)
    risk_fraction = st.slider("Risk İştahı (Kelly Fraction)", 0.1, 1.0, 0.5, step=0.05)
    st.caption("Not: 0.5 (Half-Kelly) agresif, 0.25 ise daha güvenli bir yöntemdir.")
    st.markdown("---")
    st.info("Bu araç, Elo + Form + Sakatlık verilerini harmanlayarak matematiksel değer tespiti yapar.")

# 📑 Main Navigation Tabs
tab1, tab2, tab3 = st.tabs(["📁 Günlük Bülten", "🤖 AI Analiz & Kupon", "📈 Performans"])

with tab1:
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
        st.dataframe(st.session_state['bulten'], use_container_width=True)

with tab2:
    st.header("2. AI Analiz & Kupon")
    
    # Initialize UI states
    if 'is_analyzing' not in st.session_state:
        st.session_state['is_analyzing'] = False
        
    # Two-stage trigger: If start_analysis was set, now we are actually analyzing
    if st.session_state.get('start_analysis', False):
        st.session_state['is_analyzing'] = True
        st.session_state['start_analysis'] = False
        
    # Kullanıcıya güvenli marj (Edge) seçtirme şansı verelim
    min_edge_pct = st.slider(
        "Minimum Beklenen Kâr (Edge) Oranı %", 
        min_value=0.0, max_value=30.0, value=5.0, step=1.0,
        disabled=st.session_state['is_analyzing']
    )
    st.caption("Not: Bültendeki oranların şirket kâr marjını yenmesi için en az %5 seçilmesi daha risksizdir.")

    # 🕒 Automation Status
    latest_scan = get_latest_scan()
    if latest_scan:
        st.info(f"🕒 Otomatik Tarama Aktif: Son tarama {latest_scan['last_scan']} tarihinde yapıldı.")
        if 'value_bets' not in st.session_state and not st.session_state.get('is_analyzing', False):
            if st.button("Otomatik Tarama Sonuçlarını Yükle", use_container_width=True):
                st.session_state['value_bets'] = pd.DataFrame(latest_scan['predictions'])
                st.rerun()

    if 'bulten' in st.session_state:
        # Button only triggers the rerun
        if st.button("Yapay Zeka ile Analiz Et (Manuel)", type="primary", disabled=st.session_state['is_analyzing']):
            st.session_state['start_analysis'] = True
            st.rerun()
            
    # Actual Analysis Execution
    if st.session_state.get('is_analyzing', False) and 'bulten' in st.session_state:
        try:
            with st.spinner("Maç istatistikleri ve sakatlıklar inceleniyor..."):
                value_bets_df = analyzer.analyze_fixtures(
                    st.session_state['bulten'], 
                    min_edge=min_edge_pct/100.0,
                    bankroll=BANKROLL,
                    kelly_fraction=risk_fraction
                )
                st.session_state['value_bets'] = value_bets_df
                
                # Save predictions for performance tracking
                save_predictions(value_bets_df, BANKROLL, risk_fraction, min_edge_pct)
        except Exception as e:
            st.error(f"Hata oluştu: {e}")
            import traceback
            st.code(traceback.format_exc())
        finally:
            st.session_state['is_analyzing'] = False
            st.rerun()

    if 'value_bets' in st.session_state:
        df = st.session_state['value_bets']
        if not df.empty:
            # Premium Styling CSS
            st.markdown("""
                <style>
                .match-card {
                    background-color: #f0f2f6;
                    border-radius: 10px;
                    padding: 15px;
                    margin-bottom: 15px;
                    border-left: 5px solid #2ecc71;
                    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
                }
                .match-title {
                    font-size: 18px;
                    font-weight: bold;
                    color: #2c3e50;
                }
                .metric-label {
                    font-size: 12px;
                    color: #7f8c8d;
                }
                .metric-value {
                    font-size: 16px;
                    font-weight: bold;
                    color: #27ae60;
                }
                </style>
            """, unsafe_allow_html=True)

            st.success(f"**{len(df)}** adet Değerli Bahis (Value Bet) bulundu!")
            
            # Display Results as Cards instead of DataFrame for mobile
            for idx, row in df.iterrows():
                with st.container():
                    # Custom HTML for Card
                    st.markdown(f"""
                        <div class="match-card">
                            <div class="match-title">⚽ {row['Match']}</div>
                            <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                                <div>
                                    <div class="metric-label">Tahmin</div>
                                    <div class="metric-value" style="color: #2980b9;">{row['Prediction']}</div>
                                </div>
                                <div>
                                    <div class="metric-label">AI Olasılık</div>
                                    <div class="metric-value">{row['AI_Probability']}</div>
                                </div>
                                <div>
                                    <div class="metric-label">Iddaa Oran</div>
                                    <div class="metric-value">{row['Iddaa_Odds']}</div>
                                </div>
                                <div>
                                    <div class="metric-label">Edge</div>
                                    <div class="metric-value" style="color: #e67e22;">{row['Edge']}</div>
                                </div>
                            </div>
                            <div style="margin-top: 10px; font-size: 13px;">
                                🏥 Eksikler: Ev {row['Ev_Eksik']} | Dep {row['Dep_Eksik']} | 
                                💰 Önerilen: <b>{row['Kelly_Bahis']} TL</b> ({row['Kelly_Pct']})
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

            # AI Düşünce paneli
            if 'Explanation' in df.columns:
                with st.expander("🤖 Yapay Zeka Nasıl Düşündü?"):
                    for idx, row in df.head(5).iterrows():
                        st.markdown(f"**{row['Match']} - Tahmin: {row['Prediction']}**")
                        st.info(row['Explanation'])

            # Plot the edge chart
            st.subheader("Avantaj (Edge) Grafiği")
            chart_data = df[['Match', 'Edge']].copy()
            chart_data['Edge'] = chart_data['Edge'].str.rstrip('%').astype(float)
            st.bar_chart(chart_data.set_index('Match'))

            # Kupon Önerisi (Kelly Kriteri)
            st.markdown("---")
            st.subheader("🎫 Önerilen Kuponlar")
            
            singles, system_coupon, total_stake = analyzer.build_coupon(df, bankroll=BANKROLL)
            
            if singles:
                st.markdown("### 📌 Tekli Bahisler")
                for i, bet in enumerate(singles, 1):
                    with st.container():
                        c1, c2, c3 = st.columns([3, 1, 1])
                        with c1:
                            st.markdown(f"**{i}. {bet['match']}**")
                            st.caption(f"Tahmin: {bet['prediction']} | AI: {bet['ai_prob']} | Edge: {bet['edge']}")
                        with c2:
                            st.metric("Oran", f"{bet['odds']:.2f}")
                        with c3:
                            st.metric("Bahis", f"{bet['kelly_bet']} TL")
                
                st.markdown(f"**Toplam Tekli Yatırım:** {total_stake:,.0f} TL")
            
            if system_coupon:
                st.markdown("---")
                st.markdown(f"### 🔗 Sistem Kuponu ({system_coupon['type']})")
                r1, r2, r3, r4 = st.columns(4)
                with r1:
                    st.metric("Kombine Oran", f"{system_coupon['combined_odds']:.2f}")
                with r2:
                    st.metric("AI Olasılık", system_coupon['combined_prob'])
                with r3:
                    st.metric("Yatırım", system_coupon['formatted_stake'])
                with r4:
                    st.metric("Potansiyel Kazanç", f"{system_coupon['potential_win']:,.0f} TL")
                
                # Show matches in system coupon
                with st.expander("Maç Listesi"):
                    for leg in system_coupon['legs']:
                        st.markdown(f"⚽ **{leg['match']}** - Tahmin: `{leg['prediction']}` | Oran: {leg['odds']}")
        else:
            st.warning("Değerli bahis bulunamadı.")
    else:
        st.info("Analiz için bülteni çektikten sonra butona basınız.")

with tab3:
    render_performance_tab(fetcher)

st.markdown("---")
st.caption("🚨 Uyarı: Bu sadece matematiksel tahmin ve olasılıkları analiz eden bir araçtır. %100 kesinlik garanti etmez.")
