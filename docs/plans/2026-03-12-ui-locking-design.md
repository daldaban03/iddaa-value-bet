# Tasarım Dokümanı: Analiz Sırasında UI Kilitleme (2026-03-12)

## 1. Problem Tanımı
Telefonda (mobil) kullanım sırasında, "Yapay Zeka ile Analiz Et" butonu basıldıktan sonra kullanıcılar yanlışlıkla `min_edge_pct` slider'ına (kaydırıcıya) dokunabilmektedir. Streamlit'in çalışma mantığı gereği, slider üzerindeki en ufak bir değişiklik uygulamanın yeniden yüklenmesine (rerun) ve devam eden analizin kesilmesine neden olmaktadır.

## 2. Önerilen Çözüm (Seçenek 1: Session State Kilidi)
Uygulama analiz aşamasına girdiğinde etkileşimli bileşenleri geçici olarak devre dışı bırakan bir "State Management" (Durum Yönetimi) mekanizması kurulacaktır.

### Mimari Detaylar
- **State Değişkeni**: `st.session_state['is_analyzing']` (Bool).
- **Kilitleme Noktası**: Analiz butonuna basıldığı an.
- **Kilit Açma Noktası**: `analyze_fixtures` fonksiyonu tamamlandığında veya hata aldığında (finally bloğu).

## 3. Bileşen Değişiklikleri (`app.py`)
- `min_edge_pct` slider tanımına `disabled=st.session_state.get('is_analyzing', False)` parametresi eklenecek.
- Analiz butonu mantığı, `is_analyzing` durumunu yönetecek şekilde güncellenecek.

## 4. Hata Yönetimi ve Güvenlik
Analiz sırasında beklenmedik bir hata (Exception) oluşması durumunda, arayüzün kilitli kalmaması için `is_analyzing = False` ataması mutlaka bir `try...finally` bloğu içerisinde yapılacaktır.

## 5. Başarı Kriterleri
- Buton basıldığında slider grileşmeli ve dokunulamaz olmalı.
- Analiz bittiğinde (başarılı veya başarısız) slider tekrar aktif olmalı.
- Slider'a dokunulduğunda analiz süreci hiçbir şekilde kesintiye uğramamalı.
