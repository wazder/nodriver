# Sahibinden.com Scraper Projesi

## 📋 Proje Özeti

Bu proje, **Keller Williams Karma** emlak mağazasının Sahibinden.com'daki ilanlarını otomatik olarak çekmek için geliştirilmiş bir web scraper'dır.

## 🎯 Amaç

- Sahibinden.com'un güçlü anti-bot korumasını aşmak
- Otomatik login (email + şifre)
- Email tabanlı 2FA doğrulamasını otomatik okumak (Gmail IMAP)
- Mağaza ilanlarını scrape etmek
- İlan detaylarını (fiyat, konum, açıklama, fotoğraflar) çekmek

## 🛠️ Kullanılan Teknolojiler

- **nodriver**: Undetected Chrome automation (selenium alternatifi)
- **CDP (Chrome DevTools Protocol)**: Klavye simülasyonu için
- **Gmail IMAP**: 2FA kodlarını otomatik okumak için
- **curl_cffi** (opsiyonel): Hızlı HTTP istekleri için

## 📁 Dosya Yapısı

```
example/
├── sahibinden_v2.py          # Ana scraper (en güncel versiyon)
├── sahibinden_safe.py        # Güvenli scraper (browser-only)
├── sahibinden_scraper.py     # Hibrit scraper (nodriver + curl_cffi)
├── sahibinden_simple.py      # Basit scraper
├── sahibinden_with_login.py  # Manuel login destekli scraper
├── test_detail_page.py       # Sayfa yapısı test scripti
├── sahibinden_cookies.json   # Kaydedilen cookie'ler
└── kellerwilliams_data/      # Scrape edilen veriler
    ├── listing_urls.json     # İlan URL'leri (80 ilan)
    ├── listings.json         # İlan detayları
    └── listings_detailed.json
```

## 🔐 Kimlik Bilgileri

```python
# Sahibinden Login
EMAIL = "wwazder@gmail.com"
PASSWORD = "BombaYagiyo31"

# Gmail App Password (2FA için)
GMAIL_APP_PASSWORD = "rxlkdfxwbhlanqhy"
```

## 🚀 Kullanım

```bash
cd /Users/wazder/Documents/GitHub/nodriver
python3 example/sahibinden_v2.py
```

## ✅ Tamamlanan Özellikler

1. **Browser Başlatma**
   - Headless=False (görünür browser)
   - Anti-detection flags

2. **Cookie Popup Kapatma**
   - "Kabul Et" butonunu otomatik tıklama

3. **CAPTCHA Desteği**
   - "Press and Hold" CAPTCHA algılama
   - Kullanıcı müdahalesi bekleme

4. **Otomatik Login**
   - Email alanına karakter karakter yazma (anti-paste bypass)
   - Şifre alanına TAB ile geçiş
   - CDP `dispatch_key_event` ile gerçekçi klavye simülasyonu

5. **2FA Desteği**
   - Gmail IMAP ile otomatik kod okuma
   - Son 2 dakikadaki UNSEEN mailleri kontrol
   - 6 haneli kod çıkarma

6. **İlan URL Toplama**
   - Mağaza sayfalarını tarama
   - Pagination desteği (50 ilan/sayfa)
   - **80 benzersiz ilan URL'si toplandı**

## ⚠️ Karşılaşılan Sorunlar

### 1. Copy-Paste Koruması
**Sorun:** Sahibinden, copy-paste ile girilen email/şifreleri algılıyor ve engelliyor.

**Çözüm:** CDP `dispatch_key_event` ile karakter karakter yazma:
```python
await page.send(uc.cdp.input_.dispatch_key_event(
    type_="char",
    text=char
))
```

### 2. Özel Karakterler (@ ve .)
**Sorun:** @ ve . karakterleri standart keyDown/keyUp ile yazılmıyordu.

**Çözüm:** `type_="char"` eventi kullanıldı.

### 3. 2FA Kod Girişi
**Sorun:** 6 ayrı input kutusuna (maxlength="1") kod girilemiyor - tüm CDP yöntemleri başarısız.

**Denenen Yöntemler:**
- `dispatch_key_event` (keyDown/keyUp)
- `dispatch_key_event` (type="char")
- `insert_text`
- JavaScript `execCommand('insertText')`
- Native value setter + event dispatch
- Element `send_keys()`

**Durum:** ❌ Çözülemedi - Sahibinden'in 2FA input'ları çok güçlü anti-automation korumasına sahip.

### 4. 2FA Deneme Limiti
**Son Durum:** Çok fazla başarısız 2FA denemesi yapıldığı için hesap 24 saat kilitlendi:
> "Onay kodu hakkınızı doldurdunuz. 24 saat sonra tekrar deneyiniz."

## 📊 Toplanan Veriler

- **80 ilan URL'si** `kellerwilliams_data/listing_urls.json`
- Mağaza: https://kellerwillamskarma.sahibinden.com

## 🔄 Sonraki Adımlar

1. **24 saat bekleme** - 2FA kilidi açılana kadar
2. **Manuel 2FA modu** - Kod geldiğinde kullanıcıya bildirip manuel giriş beklemek
3. **Cookie persistence** - Başarılı login sonrası cookie'leri uzun süreli saklamak
4. **İlan detayları** - URL'ler toplandı, detaylar çekilecek

## 📝 Notlar

- Sahibinden'in anti-bot koruması çok güçlü
- 2FA input kutuları özel korumaya sahip (React/Vue bazlı olabilir)
- Her denemede CAPTCHA çıkabiliyor
- Rate limiting var, çok hızlı istek atılmamalı

## 🕐 Tarih

- **Başlangıç:** 4 Şubat 2026
- **Son güncelleme:** 4 Şubat 2026
- **Durum:** 2FA kilidi nedeniyle beklemede

---

*Bu proje nodriver kütüphanesi kullanılarak geliştirilmiştir.*
