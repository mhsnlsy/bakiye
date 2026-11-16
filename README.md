# Bakiye

Google Sheets nakit/bakiye verisini ve hisse portföyünü tek ekranda birleştiren GitHub Pages uygulaması.

## GitHub Pages
Repository Settings → Pages → Deploy from a branch → `main` / `(root)`.

## Google Sheets
Sayfadaki Sheets / Bakiye sekmesinde, Google Sheets → Dosya → Paylaş → Web'de yayınla → CSV bağlantısını gir.

## İlk sürüm kapsamı
- `index.html`: responsive dashboard.
- Hisse portföyü başlangıç değerleri, Midas ekstresinin 14.11.2026 portföy özetinden alınmıştır.
- CSV üzerinden Sheets tablosu gösterimi.
- Yerel ek hareket girişi / CSV dışa aktarma.

## Veri doğruluğu notu
İlk ekran, hisse satırlarında Midas ekstre özeti ve önceki örnek hesaplamadan aktarılan referans rakamlar gösterir. Tarihsel her alışın net mevduat karşılığını doğru üretmek için tam işlem defteri, dönemsel mevduat oranları ve satışlarda lot eşleştirme motoru sonraki aşamada bağlanmalıdır. Yerel eklemeler şimdilik sadece bu tarayıcıdaki localStorage'da tutulur; kalıcı ve cihazlar arası senkronizasyon API/veritabanı gerektirir.
