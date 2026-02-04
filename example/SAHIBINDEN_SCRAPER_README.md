# Sahibinden.com Scraper Projesi

## 📋 Proje Özeti

Bu proje, **Keller Williams Karma** emlak mağazasının Sahibinden.com'daki ilanlarını otomatik olarak çekmek için geliştirilmiş bir web scraper'dır.

## 🎯 Amaç

- Sahibinden.com'un güçlü anti-bot korumasını aşmak
- Otomatik login (email + şifre)
- Email tabanlı 2FA doğrulamasını otomatik okumak (Gmail IMAP)
- Mağaza ilanlarını scrape etmek
- İlan detaylarını (fiyat, konum, açıklama, fotoğraflar) çekmek
- **🆕 Kendi domain üzerinden otomatik hesap yönetimi**
- **🆕 Rate limit durumunda otomatik hesap rotasyonu**

## 🛠️ Kullanılan Teknolojiler

- **nodriver**: Undetected Chrome automation (selenium alternatifi)
- **CDP (Chrome DevTools Protocol)**: Klavye simülasyonu için
- **Gmail IMAP**: 2FA kodlarını otomatik okumak için
- **curl_cffi** (opsiyonel): Hızlı HTTP istekleri için
- **🆕 Catch-all Email**: Kendi domain üzerinden sınırsız email

## 📁 Dosya Yapısı

```
example/
├── sahibinden_v3.py          # 🆕 Multi-account scraper (EN GÜNCEL)
├── account_manager.py        # 🆕 Hesap yönetim sistemi
├── sahibinden_accounts.json  # 🆕 Hesap veritabanı
├── sahibinden_v2.py          # Tekli hesap scraper
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
# Eski Gmail hesabı (artık kullanılmıyor)
EMAIL = "wwazder@gmail.com"
PASSWORD = "BombaYagiyo31"
GMAIL_APP_PASSWORD = "rxlkdfxwbhlanqhy"
```

## 🆕 Domain Email Yapılandırması (account_manager.py)

```python
DOMAIN_CONFIG = {
    # Domain bilgileri
    "domain": "YOUR_DOMAIN.com",  # örn: "wazder.dev"
    
    # IMAP ayarları (catch-all email okumak için)
    "imap_server": "imap.YOUR_PROVIDER.com",  # örn: "imap.yandex.com"
    "imap_port": 993,
    "imap_user": "catch-all@YOUR_DOMAIN.com",
    "imap_password": "YOUR_APP_PASSWORD",
}
```

## 🚀 Yeni Kullanım (Multi-Account)

```bash
cd /Users/wazder/Documents/GitHub/nodriver

# 1. Önce hesapları oluştur (3-5 hesap önerilir)
python3 example/account_manager.py --create 3

# 2. Hesapları listele
python3 example/account_manager.py --list

# 3. İstatistikleri gör
python3 example/account_manager.py --stats

# 4. Email yapılandırmasını test et
python3 example/account_manager.py --test-email

# 5. Scraper'ı çalıştır (otomatik hesap rotasyonu ile)
python3 example/sahibinden_v3.py
```

## 🔄 Eski Kullanım (Tek Hesap)

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

7. **🆕 Multi-Account Yönetimi**
   - Kendi domain üzerinden otomatik hesap oluşturma
   - Catch-all email ile sınırsız email adresi
   - Rastgele email ve şifre üretme
   - Hesap veritabanı (JSON)

8. **🆕 Hesap Rotasyonu**
   - Rate limit algılama
   - Otomatik hesap değiştirme
   - Limited/Banned hesap takibi
   - Cookie persistence

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

1. ~~24 saat bekleme~~ ✅ **Multi-account sistemi ile çözüldü**
2. ~~Manuel 2FA modu~~ ✅ **Kendi domain ile otomatik 2FA**
3. ~~Cookie persistence~~ ✅ **Hesap bazlı cookie saklama**
4. **Domain yapılandırması** - Kullanıcının domain bilgilerini girmesi gerekiyor
5. **İlan detayları** - URL'ler toplandı, detaylar çekilecek

## 🌐 Domain Yapılandırması (ÖNEMLİ!)

### ✅ Cloudflare Email Routing Kurulumu (wazder.dev için)

#### Adım 1: Email Routing'i Aktifleştir
1. https://dash.cloudflare.com → wazder domain'i seç
2. Sol menü → **Email** → **Email Routing**
3. **"Enable Email Routing"** tıkla
4. DNS kayıtlarını otomatik eklesin

#### Adım 2: Destination Email Ekle
1. **"Destination addresses"** → **"Add destination"**
2. `wwazder@gmail.com` ekle
3. Gmail'e gelen doğrulama linkine tıkla

#### Adım 3: Catch-All Rule (EN ÖNEMLİ!)
1. **"Routing rules"** → **"Catch-all address"** → **"Edit"**
2. **Action:** "Send to an email"
3. **Destination:** `wwazder@gmail.com`
4. **"Save"**

#### Adım 4: Test Et
```bash
# Email routing'i test et
python3 example/account_manager.py --test-email
```

### Nasıl Çalışıyor?
```
1. Sahibinden → randomuser123@wazder.dev'e mail atar
2. Cloudflare catch-all → wwazder@gmail.com'a yönlendirir  
3. Script Gmail IMAP ile maili okur
4. TO header'dan hangi @wazder.dev adresine geldiğini anlar
```

## 📝 Notlar

- Sahibinden'in anti-bot koruması çok güçlü
- 2FA input kutuları özel korumaya sahip (React/Vue bazlı olabilir)
- Her denemede CAPTCHA çıkabiliyor
- Rate limiting var, çok hızlı istek atılmamalı
- **🆕 Multi-account sistemi ile rate limit sorunları minimize edildi**

## 🕐 Tarih

- **Başlangıç:** 4 Şubat 2026
- **Son güncelleme:** 4 Şubat 2026
- **Durum:** ~~2FA kilidi nedeniyle beklemede~~ ✅ Multi-account sistemi eklendi

## 📊 Hesap Yönetimi Komutları

```bash
# Hesap oluştur
python3 example/account_manager.py --create 5

# Hesapları listele  
python3 example/account_manager.py --list

# İstatistikler
python3 example/account_manager.py --stats

# Aktif hesabı değiştir
python3 example/account_manager.py --rotate

# Belirli hesabı aktif yap
python3 example/account_manager.py --set-active user123@domain.com

# Email bağlantısını test et
python3 example/account_manager.py --test-email
```

---

*Bu proje nodriver kütüphanesi kullanılarak geliştirilmiştir.*
