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
tab1, tab2, tab3 = st.tabs(["📊 Günlük Bülten", "🤖 AI Analiz & Kupon", "📈 Performans"])

with tab1:
    st.header("📅 Günlük Maç Bülteni")
    
    # UI: Clear session state button
    if 'bulten' in st.session_state:
        if st.button("🗑️ Bülteni Temizle", use_container_width=False):
            del st.session_state['bulten']
            st.rerun()

    # 🕒 Search in Bulletin
    if 'bulten' in st.session_state:
        b_search = st.text_input("🔍 Bülten İçinde Ara", placeholder="Takım ismi girin...")
        display_bulten = st.session_state['bulten']
        if b_search:
            display_bulten = display_bulten[
                display_bulten['Home_Team'].str.contains(b_search, case=False, na=False) |
                display_bulten['Away_Team'].str.contains(b_search, case=False, na=False)
            ]
        st.dataframe(display_bulten, use_container_width=True, hide_index=True)
    
    # 🕒 Load from Background Scan
    latest_scan = get_latest_scan()
    if latest_scan and 'bulten' in latest_scan and latest_scan['bulten']:
        if st.button("Otomatik Tarama Bültenini Yükle", use_container_width=True):
            st.session_state['bulten'] = pd.DataFrame(latest_scan['bulten'])
            st.success(f"Otomatik taramadan ({latest_scan['last_scan']}) {len(st.session_state['bulten'])} maç yüklendi.")
            st.rerun()

    if st.button("Bülteni Çek (Manuel)", type="primary"):
        with st.spinner("Bülten indiriliyor..."):
            try:
                # Fetch daily data
                bulten_df = scraper.fetch_daily_bulten()
                
                st.session_state['bulten'] = bulten_df
                st.success(f"{len(bulten_df)} maç başarıyla çekildi.")
            except Exception as e:
                st.error(f"Hata: {e}")

    pass # Bulletin is already displayed in the search section above

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
            # Premium Glassmorphism Styling
            st.markdown("""
                <style>
                /* Google Fonts - Inter & Outfit */
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Outfit:wght@500;800&display=swap');
                
                html, body, [class*="st-"] {
                    font-family: 'Inter', sans-serif;
                }
                
                h1, h2, h3, .match-title {
                    font-family: 'Outfit', sans-serif;
                }

                .match-card {
                    background: rgba(30, 41, 59, 0.7);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    padding: 24px;
                    margin-bottom: 24px;
                    border-left: 8px solid #38bdf8; /* Cyan */
                    box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                }
                .match-card:hover {
                    transform: scale(1.02);
                    border-left: 8px solid #facc15; /* Gold on hover */
                    background: rgba(30, 41, 59, 0.9);
                }
                .match-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 20px;
                }
                .match-title {
                    font-size: 22px;
                    font-weight: 800;
                    color: #f8fafc;
                    line-height: 1.2;
                    margin-right: 10px;
                }
                .prediction-badge {
                    background: linear-gradient(135deg, #10b981, #059669); /* Emerald */
                    color: white;
                    padding: 6px 16px;
                    border-radius: 99px;
                    font-size: 13px;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3);
                }
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 20px;
                    margin-top: 20px;
                    padding: 15px;
                    background: rgba(15, 23, 42, 0.6);
                    border-radius: 12px;
                }
                .metric-item {
                    display: flex;
                    flex-direction: column;
                }
                .metric-label {
                    font-size: 10px;
                    text-transform: uppercase;
                    font-weight: 700;
                    color: #94a3b8;
                    letter-spacing: 1.2px;
                    margin-bottom: 6px;
                }
                .metric-value {
                    font-size: 20px;
                    font-weight: 800;
                    color: #f1f5f9;
                }
                .kelly-section {
                    margin-top: 20px;
                    padding: 16px;
                    background: linear-gradient(135deg, rgba(250, 204, 21, 0.1), rgba(250, 204, 21, 0.2));
                    border: 1px solid rgba(250, 204, 21, 0.3);
                    border-radius: 12px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .kelly-amount {
                    font-size: 24px;
                    font-weight: 900;
                    color: #facc15;
                    text-shadow: 0 0 20px rgba(250, 204, 21, 0.4);
                }
                .date-badge {
                    font-size: 12px;
                    color: #94a3b8;
                    margin-top: 5px;
                }
                </style>
            """, unsafe_allow_html=True)

            st.success(f"**{len(df)}** adet Değerli Bahis (Value Bet) bulundu!")
            
            # UX: Search and Filter
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                search_query = st.text_input("🔍 Maç veya Takım Ara", placeholder="Örn: Galatasaray, Premier League...")
            with col_s2:
                sort_by = st.selectbox(
                    "Sıralama",
                    ["Beklenen Kâr (Edge) - Azalan", "Tarih - En Yakın", "Kelly Yatırımı - Azalan"],
                    index=0
                )
            
            # Application of search filter
            if search_query:
                df = df[df['Match'].str.contains(search_query, case=False, na=False)]
            
            # Prepare numeric columns for sorting with safety checks
            df_display = df.copy()
            if 'Edge' in df_display.columns:
                df_display['Edge_Val'] = df_display['Edge'].apply(lambda x: float(str(x).rstrip('%')) if isinstance(x, str) else float(x))
            else:
                df_display['Edge_Val'] = 0.0

            if 'Kelly_Bahis' in df_display.columns:
                df_display['Kelly_Val'] = df_display['Kelly_Bahis'].apply(lambda x: float(str(x).replace(',', '')) if isinstance(x, str) else float(x))
            else:
                df_display['Kelly_Val'] = 0.0
            
            if sort_by == "Beklenen Kâr (Edge) - Azalan":
                df_display = df_display.sort_values(by='Edge_Val', ascending=False)
            elif sort_by == "Tarih - En Yakın":
                df_display = df_display.sort_values(by='Date', ascending=True)
            elif sort_by == "Kelly Yatırım - Azalan":
                df_display = df_display.sort_values(by='Kelly_Val', ascending=False)
            elif sort_by == "Tarih - En Uzak":
                df_display = df_display.sort_values(by='Date', ascending=False)
            
            # Display Results as Cards
            for idx, row in df_display.iterrows():
                with st.container():
                    st.markdown(f"""
                        <div class="match-card">
                            <div class="match-header">
                                <div class="match-title">⚽ {row['Match']}</div>
                                <div class="prediction-badge">{row['Prediction']}</div>
                            </div>
                            <div style="font-size: 12px; margin-bottom: 10px; opacity: 0.8;">📅 Tarih (TSİ): {row['Date']}</div>
                            <div class="stats-grid">
                                <div class="metric-item">
                                    <div class="metric-label">AI Olasılık</div>
                                    <div class="metric-value">{row['AI_Probability']}</div>
                                </div>
                                <div class="metric-item">
                                    <div class="metric-label">Iddaa Oran</div>
                                    <div class="metric-value">{row['Iddaa_Odds']}</div>
                                </div>
                                <div class="metric-item">
                                    <div class="metric-label">Avantaj (Edge)</div>
                                    <div class="metric-value" style="color: #e67e22;">{row['Edge']}</div>
                                </div>
                                <div class="metric-item">
                                    <div class="metric-label">Sakat/Cezalı</div>
                                    <div class="metric-value">Ev {row['Ev_Eksik']} | Dep {row['Dep_Eksik']}</div>
                                </div>
                            </div>
                            <div class="kelly-section">
                                <div>
                                    <div class="metric-label">Önerilen Kelly Yatırımı</div>
                                    <div style="font-size: 12px; opacity: 0.8;">Bankroll Oranı: {row['Kelly_Pct']}</div>
                                </div>
                                <div class="kelly-amount">{row['Kelly_Bahis']} TL</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

            # AI Düşünce paneli
            if 'Explanation' in df.columns:
                with st.expander("🤖 Yapay Zeka Nasıl Düşündü?"):
                    for idx, row in df.iterrows():
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
