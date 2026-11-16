# Bakiye

Tek ana sayfada toplam varlık, hisse portföyü, fonlar, banka bakiyeleri, döviz, altın ve aylık yükümlülükleri gösteren GitHub Pages paneli.

## Canlı sayfa
https://mhsnlsy.github.io/bakiye/

## Veri modeli
- `data/balance.json`: Google Sheets'ten gelen hesap bakiyeleri ve aylık ödemeler için başlangıç verisi.
- `data/positions.json`: Midas portföyündeki hisse ve fon adetleri ile ortalama maliyetler.
- `data/quotes.json`: Son doğrulanmış fiyat önbelleği ve kaynak tarihi.
- `index.html`: Tüm kaynakları bir araya getirir, toplam varlığı ve ödemeler sonrası net bakiyeyi hesaplar.

## Toplam bakiye hesabı
Midas satırı, Midas'taki hisse/fon pozisyonlarının hesap üst bilgisidir. Bu nedenle toplam varlığa Midas hesabının yuvarlak bakiyesi ayrıca eklenmez; pozisyonlar tek tek değerlenir. Böylece mükerrer sayım engellenir.

## Google Sheets güncellemesi
Sayfa, verilen Google Sheets CSV dışa aktarma adresini açılışta ve 5 dakikada bir kontrol eder. Bunun çalışması için Google Sheets dosyasının bağlantıya sahip görüntüleyicilere açık veya web'de CSV olarak yayınlanmış olması gerekir. Tarayıcı erişimi başarısız olursa son kayıtlı başlangıç değerleri korunur.

## Fintables fiyat kaynağı
- Hisse tablosunda Fintables Radar birincil referans sayfası olarak bağlanmıştır: https://fintables.com/radar/hisse-senetleri
- Fintables Radar'dan dışa aktarılan CSV, hisse/fon tablosuna aktarılabilir; içe aktarılan fiyatlar o tarayıcıda saklanır ve toplam bakiye yeniden hesaplanır.
- Şu anki fiyat önbelleği Midas ekstresinin 14.11.2026 kapanış fiyatlarından oluşur. Fintables fiyat verisi doğrulanmadan yeni fiyat gibi gösterilmez. Radar sayfasına doğrudan bağlanabilen ve herkese açık belgelenmiş bir BIST fiyat API'si olmadığı için otomatik API fiyat güncellemesi bu sürümde etkin değildir.

## Yayınlama
`.github/workflows/pages.yml`, `main` dalına her push'ta GitHub Pages dağıtımını çalıştırır.

## Gizlilik
GitHub deposu herkese açık olduğu için bu sayfaya ve `data/*.json` dosyalarına yazılan bakiye tutarları da herkese açıktır. Özel finansal bilgiler içeren kullanım için erişimi kısıtlı bir barındırma ve kimlik doğrulama katmanı gerekir.
