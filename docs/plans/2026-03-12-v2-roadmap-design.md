# Tasarım Dokümanı: Iddaa Value Bet AI v2.0 (2026-03-12)

## 1. Genel Amaç
Uygulamanın mobil kullanılabilirliğini artırmak, tahmin doğruluğunu şeffaf bir şekilde takip etmek ve yapay zeka modellerini güncel futbol verileriyle modernize etmek.

## 2. Teknik Bileşenler

### 2.1 UI/UX: Premium & Mobil Odaklı Tasarım
- **Navigasyon**: `st.tabs` kullanılarak uygulama 3 ana bölüme ayrılacak:
    - 📁 **Bülten**: Maç listesi ve veri çekme işlemleri.
    - 🤖 **Analiz & Kupon**: Yapay zeka sonuçları ve Kelly önerileri.
    - 📈 **Performans**: Geçmiş başarı oranları ve istatistikler.
- **Kontrol Merkezi (Sidebar)**: `st.sidebar` içine `BANKROLL`, `Kelly Oranı` ve `Min Edge` gibi ayarlar taşınarak ana ekran temizlenecek.
- **Sonuç Kartları**: Maç sonuçları tablo yerine `st.container` içerisinde, takım logoları (emoji) ve renkli metriklerle "Kart" yapısında gösterilecek.

### 2.2 Performans Takip Sistemi (Option A)
- **Veri Saklama**: Analiz her bittiğinde `data/predictions/YYYY-MM-DD_HHMM.json` formatında kayıt alınacak.
- **Doğrulama**: `DataFetcher` modülü, geçmiş tahmin dosyalarındaki maçların gerçek skorlarını `football-data.co.uk` veya Iddaa üzerinden sorgulayacak.
- **Metrikler**: "Total ROI", "Yüzdesel Başarı", "En Çok Kazandıran Lig" gibi bilgiler hesaplanacak.

### 2.3 Model Modernizasyonu
- **Veri Güncelleme**: `HistoricalDataFetcher.TRAINING_SEASONS` listesine `2425` (güncel sezon) eklenecek.
- **Eğitim**: XGBoost ve MLP modelleri güncel form ve Elo trendleriyle yeniden eğitilip `joblib` ile kaydedilecek.

## 3. Veri Akış Şeması
1. **Giriş**: Kullanıcı bülteni çeker.
2. **İşlem**: Analiz butonu ile AI çalışır -> Sonuçlar ekranda "Kart" olarak belirir -> Tahminler JSON olarak diske yazılır.
3. **Takip**: Performans sekmesine tıklandığında diskteki eski JSON'lar okunur -> Gerçek skorlarla eşleştirilir -> Dashboard güncellenir.

## 4. Başarı Kriterleri
- Uygulamanın mobilde tek ekranda (kaydırmadan) ana kumandaya sahip olması.
- Kullanıcının "AI ne kadar başarılı?" sorusuna tek tıkla yanıt alabilmesi.
- Modellerin 2025 dinamiklerini (yeni transferler, takım formları) yansıtması.
