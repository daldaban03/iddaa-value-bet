import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from utils.background_worker import BackgroundAnalyzer, get_latest_scan
import importlib
import sys
import scraper
import data_fetcher
import predictor
import analyzer
import performance_ui
import utils.persistence as persistence

# 🕒 Start Background Automation
@st.cache_resource
def start_automation(ver="1.5-quality-audit"):
    worker = BackgroundAnalyzer(interval_seconds=900)  # 15 mins
    if not worker.is_alive():
        worker.start()
    return worker

worker = start_automation(ver="1.8-mapping-fix")

st.set_page_config(
    page_title="Iddaa Value Bet AI",
    page_icon="⚽",
    layout="wide"
)

# 🎨 Premium Global CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Outfit:wght@500;800&display=swap');
    
    /* Simplified Global Font System */
    .stApp, .stApp p, .stApp label, .stApp button, .stApp input {
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, .match-title {
        font-family: 'Outfit', sans-serif !important;
    }

    /* Expander Universal Styling */
    .stExpander {
        background: rgba(30, 41, 59, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        margin-top: 10px !important;
    }
    
    /* Audit section styling */
    .audit-section {
        margin-top: 15px;
        padding: 12px;
        background: rgba(15, 23, 42, 0.4);
        border-radius: 8px;
        border-left: 3px solid #64748b;
        font-size: 12px;
        color: #94a3b8;
        line-height: 1.4;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Iddaa Value Bet AI Analyzer")
st.markdown("""
Bu araç, seçili maçların **Yapay Zeka** modeli (Elo + Form + Transfermarkt Sakatlık Analizi) ile hesaplanmış kazanma ihtimallerini, 
**iddaa** oranları ile karşılaştırarak matematiksel olarak kârlı **Value Bet (Değerli Bahis)** fırsatlarını tespit eder.
""")

# Initialize modules once and cache them for the entire server session
@st.cache_resource
def load_modules(ver="1.6-force-reload"):
    # Force reload modules to pick up file changes on Streamlit Cloud
    importlib.reload(scraper)
    importlib.reload(data_fetcher)
    importlib.reload(predictor)
    importlib.reload(analyzer)
    
    val_scraper = scraper.IddaaScraper()
    val_fetcher = data_fetcher.HistoricalDataFetcher()
    val_predictor = predictor.Predictor(val_fetcher)
    val_analyzer = analyzer.ValueAnalyzer(val_predictor)
    
    # Debug: Confirm version in logs
    print(f"  [System] Modules reloaded (Ver: {ver})")
    sys.stdout.flush()
    
    return val_scraper, val_fetcher, val_predictor, val_analyzer

scraper, fetcher, predictor, analyzer = load_modules(ver="1.9-hard-reset")

# ⚙️ Sidebar Settings
with st.sidebar:
    st.header("⚙️ Ayarlar")
    BANKROLL = st.number_input("Sermaye (TL)", value=100000, step=1000)
    # Default risk fraction (half-Kelly is 0.5)
    risk_fraction = st.slider("Risk İştahı (Kelly Fraction)", 0.1, 1.0, 0.5, step=0.05)
    st.caption("Not: 0.5 (Half-Kelly) agresif, 0.25 ise daha güvenli bir yöntemdir.")
    st.markdown("---")
    st.info("Bu araç, Elo + Form + Sakatlık verilerini harmanlayarak matematiksel değer tespiti yapar.")
    
    if st.button("🔄 Sistemi Sıfırla (Cache Clear)", use_container_width=True):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

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
        min_value=0.0, max_value=30.0, value=15.0, step=1.0,
        disabled=st.session_state['is_analyzing']
    )
    st.caption("Not: Bültendeki oranların şirket kâr marjını yenmesi için en az %15 seçilmesi daha risksizdir.")

    # 📅 Date Filter
    date_filter = st.selectbox(
        "Analiz Edilecek Maç Zamanı",
        ["Tümü", "Sadece Bugün", "Önümüzdeki 2 Gün"],
        index=0,
        disabled=st.session_state['is_analyzing']
    )

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
                target_df = st.session_state['bulten'].copy()
                
                # Apply Date Filtering
                if date_filter != "Tümü":
                    target_df['Date_DT'] = pd.to_datetime(target_df['Date'], errors='coerce')
                    target_df = target_df.dropna(subset=['Date_DT'])
                    # Turkey Time (UTC+3)
                    trt = timezone(timedelta(hours=3))
                    today = datetime.now(trt)
                    
                    if date_filter == "Sadece Bugün":
                        target_df = target_df[target_df['Date_DT'].dt.date == today.date()]
                    elif date_filter == "Önümüzdeki 2 Gün":
                        # Compare dates only to avoid timezone issues with pd.to_datetime
                        today_date = today.date()
                        two_days_later = today_date + timedelta(days=2)
                        target_df = target_df[(target_df['Date_DT'].dt.date >= today_date) & (target_df['Date_DT'].dt.date <= two_days_later)]

                if target_df.empty:
                    st.warning(f"Seçilen kriterlere ({date_filter}) uygun maç bulunamadı.")
                    st.session_state['is_analyzing'] = False
                    st.stop() # Abort execution of the rest of the block

                value_bets_df = analyzer.analyze_fixtures(
                    target_df, 
                    min_edge=min_edge_pct/100.0,
                    bankroll=BANKROLL,
                    kelly_fraction=risk_fraction
                )
                st.session_state['value_bets'] = value_bets_df
                
                # Save predictions for performance tracking
                persistence.save_predictions(value_bets_df, BANKROLL, risk_fraction, min_edge_pct)
        except Exception as e:
            st.error(f"Hata oluştu: {e}")
            import traceback
            st.code(traceback.format_exc())
            st.session_state['is_analyzing'] = False
        finally:
            # Only rerun if we actually found something to display
            if 'value_bets' in st.session_state and st.session_state.get('is_analyzing'):
                st.session_state['is_analyzing'] = False
                st.rerun()
            else:
                st.session_state['is_analyzing'] = False

    if 'value_bets' in st.session_state:
        df = st.session_state['value_bets']
        if not df.empty:
            # Premium Styling CSS
            # Premium Component Styling (Localized)
            st.markdown("""
                <style>
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
                    white-space: nowrap;
                    flex-shrink: 0;
                }
                .metric-label {
                    font-size: 11px;
                    text-transform: uppercase;
                    font-weight: 700;
                    color: #cbd5e1;
                    letter-spacing: 1.2px;
                    margin-bottom: 6px;
                }
                .metric-value {
                    font-size: 20px;
                    font-weight: 800;
                    color: #f8fafc;
                }
                .kelly-section {
                    margin-top: 24px;
                    padding: 20px;
                    background: linear-gradient(135deg, rgba(250, 204, 21, 0.15), rgba(250, 204, 21, 0.05));
                    border: 1px solid rgba(250, 204, 21, 0.4);
                    border-radius: 12px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 15px;
                }
                .kelly-amount {
                    font-size: 26px;
                    font-weight: 900;
                    color: #facc15;
                    text-shadow: 0 0 20px rgba(250, 204, 21, 0.4);
                    white-space: nowrap;
                }
                .date-badge {
                    font-size: 13px;
                    font-weight: 600;
                    color: #f1f5f9;
                    background: rgba(255, 255, 255, 0.1);
                    padding: 4px 10px;
                    border-radius: 6px;
                    display: inline-block;
                    margin-bottom: 12px;
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
                            <div class="date-badge">📅 {row['Date']} (TSİ)</div>
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
                                <div class="metric-item">
                                    <div class="metric-label">Veri Kalitesi</div>
                                    <div class="metric-value">{row['Veri_Kalitesi']}</div>
                                </div>
                            </div>
                            <div class="audit-section">
                                <b>🔍 Veri Denetimi:</b><br/>
                                {row['Veri_Detayi'].replace('\n', '<br/>')}
                            </div>
                            <div class="kelly-section">
                                <div>
                                    <div class="metric-label" style="color: #fde047;">Önerilen Kelly Yatırımı</div>
                                    <div style="font-size: 13px; opacity: 0.9; color: #f1f5f9; font-weight: 600;">Bankroll Oranı: {row['Kelly_Pct']}</div>
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
                            quality_str = bet.get('quality', '🔴 Bilinmiyor')
                            audit_str = bet.get('quality_audit', '').replace('\n', ' | ')
                            st.caption(f"Tahmin: {bet['prediction']} | AI: {bet['ai_prob']} | Edge: {bet['edge']} | Veri: {quality_str}")
                            if audit_str:
                                st.markdown(f"<div style='font-size: 11px; color: #94a3b8;'>📋 {audit_str}</div>", unsafe_allow_html=True)
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
                with st.expander("📋 Seçilen Maçların Listesi"):
                    for leg in system_coupon['legs']:
                        quality_str = leg.get('quality', '🔴 Bilinmiyor')
                        audit_str = leg.get('quality_audit', '').replace('\n', ' | ')
                        st.markdown(f"⚽ **{leg['match']}** - Tahmin: `{leg['prediction']}` | Oran: {leg['odds']} | Veri: {quality_str}")
                        if audit_str:
                            st.markdown(f"<div style='font-size: 11px; color: #94a3b8; margin-left: 25px;'>📋 {audit_str}</div>", unsafe_allow_html=True)
        else:
            st.warning("Değerli bahis bulunamadı.")
    else:
        if 'bulten' not in st.session_state:
            st.info("Analiz için bülteni çektikten sonra butona basınız.")
        else:
            st.info("Analiz sonuçlarını görmek için 'AI ile Analiz Et' butonuna basınız.")

with tab3:
    performance_ui.render_performance_tab(fetcher)

st.markdown("---")
st.caption("🚨 Uyarı: Bu sadece matematiksel tahmin ve olasılıkları analiz eden bir araçtır. %100 kesinlik garanti etmez.")
