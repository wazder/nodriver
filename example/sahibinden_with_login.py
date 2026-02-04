"""
Sahibinden.com Scraper with Login & Session Persistence
=======================================================
- İlk çalıştırmada manuel login yaparsın (2FA dahil)
- Cookie'ler kaydedilir
- Sonraki çalıştırmalarda otomatik session restore edilir
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from curl_cffi import requests as curl_requests

import nodriver as uc

# Cookie dosyası
COOKIE_FILE = Path(__file__).parent / "sahibinden_cookies.json"
DATA_DIR = Path(__file__).parent / "kellerwilliams_data"


class SahibindenAuthenticatedScraper:
    """Session persistence ile authenticated scraper"""
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.cookies = {}
        self.curl_session = None
        
    async def start(self):
        """Browser başlat ve session'ı restore et veya login yap"""
        print("=" * 60)
        print("🏠 SAHİBİNDEN.COM AUTHENTICATED SCRAPER")
        print("=" * 60)
        
        self.browser = await uc.start(headless=False)  # Headless=False for login
        
        # Ana sayfaya git
        print("\n🌐 Sahibinden.com'a bağlanılıyor...")
        self.page = await self.browser.get("https://www.sahibinden.com")
        await asyncio.sleep(3)
        
        # Çerez popup'ını kapat
        await self._close_cookie_popup()
        
        # Kayıtlı cookie var mı kontrol et
        if await self._load_cookies():
            print("✅ Kaydedilmiş session yüklendi!")
            # Session'ın geçerli olup olmadığını kontrol et
            if await self._verify_session():
                print("✅ Session geçerli, giriş yapılmış!")
                await self._setup_curl()
                return True
            else:
                print("⚠️ Session expire olmuş, yeniden login gerekiyor...")
        
        # Manuel login gerekiyor
        await self._manual_login()
        await self._setup_curl()
        return True
    
    async def _close_cookie_popup(self):
        """Çerez popup'ını kapat"""
        try:
            accept_btn = await self.page.find("Kabul Et", timeout=3)
            if accept_btn:
                await accept_btn.click()
                await asyncio.sleep(1)
                print("🍪 Çerez popup'ı kapatıldı")
        except:
            pass
    
    async def _load_cookies(self) -> bool:
        """Kaydedilmiş cookie'leri yükle"""
        if not COOKIE_FILE.exists():
            print("📁 Kayıtlı cookie dosyası bulunamadı")
            return False
        
        try:
            with open(COOKIE_FILE, 'r') as f:
                saved_data = json.load(f)
            
            cookies = saved_data.get('cookies', [])
            saved_time = saved_data.get('saved_at', '')
            
            print(f"📁 Cookie dosyası bulundu (kaydedilme: {saved_time})")
            print(f"   {len(cookies)} cookie yükleniyor...")
            
            # Cookie'leri browser'a set et
            for cookie in cookies:
                try:
                    # CDP ile cookie set et
                    await self.page.send(uc.cdp.network.set_cookie(
                        name=cookie['name'],
                        value=cookie['value'],
                        domain=cookie.get('domain', '.sahibinden.com'),
                        path=cookie.get('path', '/'),
                        secure=cookie.get('secure', True),
                        http_only=cookie.get('httpOnly', False)
                    ))
                except Exception as e:
                    pass  # Bazı cookie'ler set edilemeyebilir
            
            # Sayfayı yenile
            await self.page.reload()
            await asyncio.sleep(3)
            
            return True
            
        except Exception as e:
            print(f"❌ Cookie yükleme hatası: {e}")
            return False
    
    async def _verify_session(self) -> bool:
        """Session'ın geçerli olup olmadığını kontrol et"""
        try:
            # Mevcut URL'yi kontrol et
            current_url = await self.page.evaluate("window.location.href")
            print(f"   📍 Mevcut URL: {current_url}")
            
            # Login sayfasındaysak henüz giriş yapılmamış
            if 'giris' in str(current_url).lower() or 'login' in str(current_url).lower():
                return False
            
            # Çoklu yöntemle login kontrolü yap
            login_check = await self.page.evaluate("""
                (() => {
                    const result = {
                        isLoggedIn: false,
                        method: '',
                        details: ''
                    };
                    
                    // Yöntem 1: "Çıkış" veya "Hesabım" linki var mı?
                    const exitLink = document.querySelector('a[href*="cikis"], a[href*="logout"]');
                    if (exitLink) {
                        result.isLoggedIn = true;
                        result.method = 'exit_link';
                        result.details = 'Çıkış linki bulundu';
                        return result;
                    }
                    
                    // Yöntem 2: Hesabım linki
                    const accountLink = document.querySelector('a[href*="hesabim"]');
                    if (accountLink && !document.querySelector('a[href*="giris"]')) {
                        result.isLoggedIn = true;
                        result.method = 'account_link';
                        result.details = 'Hesabım linki bulundu';
                        return result;
                    }
                    
                    // Yöntem 3: Kullanıcı bilgisi alanı
                    const userArea = document.querySelector('.user-info, .username-info-area, .account-user, [class*="userInfo"], [class*="myAccount"]');
                    if (userArea && userArea.innerText.trim().length > 0) {
                        result.isLoggedIn = true;
                        result.method = 'user_area';
                        result.details = userArea.innerText.trim().substring(0, 50);
                        return result;
                    }
                    
                    // Yöntem 4: Login butonu YOK ise
                    const loginBtn = document.querySelector('a[href*="giris"], .login-register, [class*="login"]');
                    const bodyText = document.body.innerText;
                    if (!loginBtn && (bodyText.includes('Hesabım') || bodyText.includes('Çıkış Yap'))) {
                        result.isLoggedIn = true;
                        result.method = 'no_login_btn';
                        result.details = 'Giriş butonu yok ve hesap metni var';
                        return result;
                    }
                    
                    // Yöntem 5: Body'de "Giriş Yap" metni var mı?
                    if (!bodyText.includes('Giriş Yap') && !bodyText.includes('Üye Ol')) {
                        // Ana sayfadayken "Giriş Yap" yoksa muhtemelen giriş yapılmış
                        result.isLoggedIn = true;
                        result.method = 'no_login_text';
                        result.details = 'Giriş Yap metni bulunamadı';
                        return result;
                    }
                    
                    return result;
                })()
            """)
            
            # Nodriver value extraction
            is_logged_in = False
            method = ''
            details = ''
            
            if isinstance(login_check, list):
                for item in login_check:
                    if isinstance(item, list) and len(item) == 2:
                        key, val = item
                        if key == 'isLoggedIn':
                            is_logged_in = val.get('value', False) if isinstance(val, dict) else val
                        elif key == 'method':
                            method = val.get('value', '') if isinstance(val, dict) else val
                        elif key == 'details':
                            details = val.get('value', '') if isinstance(val, dict) else val
            elif isinstance(login_check, dict):
                is_logged_in = login_check.get('isLoggedIn', False)
                method = login_check.get('method', '')
                details = login_check.get('details', '')
            
            if is_logged_in:
                print(f"   ✅ Login doğrulandı ({method}): {details}")
                return True
            
            print(f"   ❌ Login bulunamadı")
            return False
            
        except Exception as e:
            print(f"   Session kontrol hatası: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _manual_login(self):
        """Manuel login - kullanıcı browser'da login yapar"""
        print("\n" + "=" * 60)
        print("🔐 MANUEL LOGIN GEREKİYOR")
        print("=" * 60)
        print("""
Lütfen açılan tarayıcıda:
1. Sahibinden.com'a giriş yapın
2. 2FA doğrulamasını tamamlayın
3. Giriş yaptıktan sonra herhangi bir sayfaya gidin (ana sayfa vs.)

""")
        
        # Login sayfasına git
        await self.page.get("https://www.sahibinden.com/giris")
        await asyncio.sleep(2)
        
        # Kullanıcının login yapmasını bekle
        print("⏳ Login yapmanızı bekliyorum...")
        print("   Tarayıcıda login yapın, sonra buraya gelip ENTER'a basın.\n")
        
        # Kullanıcının ENTER'a basmasını bekle
        import sys
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: input("   >>> Login tamamlandıysa ENTER'a basın: "))
        
        # Ana sayfaya git ve session kontrol et
        print("\n🔄 Session kontrol ediliyor...")
        await self.page.get("https://www.sahibinden.com")
        await asyncio.sleep(3)
        
        if await self._verify_session():
            print("\n✅ Login başarılı!")
            # Cookie'leri kaydet
            await self._save_cookies()
        else:
            print("\n⚠️ Login tespit edilemedi ama devam ediyoruz...")
            print("   (Eğer gerçekten login yaptıysanız, cookie'ler yine de kaydedilecek)")
            await self._save_cookies()
    
    async def _save_cookies(self):
        """Mevcut cookie'leri dosyaya kaydet"""
        try:
            # JS ile cookie al
            cookie_str = await self.page.evaluate("document.cookie")
            
            # Cookie string'ini parse et
            cookies = []
            for item in str(cookie_str).split(';'):
                item = item.strip()
                if '=' in item:
                    name, value = item.split('=', 1)
                    cookies.append({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.sahibinden.com',
                        'path': '/'
                    })
            
            # Dosyaya kaydet
            save_data = {
                'cookies': cookies,
                'saved_at': datetime.now().isoformat(),
                'cookie_count': len(cookies)
            }
            
            with open(COOKIE_FILE, 'w') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 {len(cookies)} cookie kaydedildi: {COOKIE_FILE}")
            
            self.cookies = {c['name']: c['value'] for c in cookies}
            
        except Exception as e:
            print(f"❌ Cookie kaydetme hatası: {e}")
    
    async def _setup_curl(self):
        """curl_cffi session'ı hazırla"""
        # JS'den cookie al
        cookie_str = await self.page.evaluate("document.cookie")
        self.cookies = {}
        for item in str(cookie_str).split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                self.cookies[name.strip()] = value.strip()
        
        self.curl_session = curl_requests.Session(impersonate="chrome120")
        self.curl_session.cookies.update(self.cookies)
        self.curl_session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            "Referer": "https://www.sahibinden.com/"
        })
        print(f"⚡ curl_cffi hazır ({len(self.cookies)} cookie)")
    
    async def get_store_listings(self, store_url: str, max_pages: int = 10) -> list:
        """Mağaza ilanlarını listele"""
        print(f"\n🏪 Mağaza taranıyor: {store_url}")
        
        all_urls = []
        page_num = 0
        
        while page_num < max_pages:
            offset = page_num * 50
            url = f"{store_url}?pagingOffset={offset}" if page_num > 0 else store_url
            
            print(f"   📄 Sayfa {page_num + 1}: {url[:60]}...")
            
            await self.page.get(url)
            await asyncio.sleep(3)
            
            # İlan linklerini çek
            links_js = """
            (() => {
                const links = [];
                document.querySelectorAll('a[href*="/ilan/"]').forEach(a => {
                    const href = a.href;
                    if (href.includes('/ilan/') && href.includes('/detay')) {
                        links.push(href);
                    }
                });
                return [...new Set(links)];
            })()
            """
            
            result = await self.page.evaluate(links_js)
            urls = self._flatten_js_result(result)
            
            if not urls:
                print(f"   ✓ Sayfa {page_num + 1}: 0 ilan (tarama bitti)")
                break
            
            all_urls.extend(urls)
            print(f"   ✓ Sayfa {page_num + 1}: {len(urls)} ilan bulundu")
            
            page_num += 1
            await asyncio.sleep(2)
        
        unique_urls = list(set(all_urls))
        print(f"\n📋 Toplam {len(unique_urls)} benzersiz ilan bulundu")
        return unique_urls
    
    def _flatten_js_result(self, result) -> list:
        """Nodriver JS sonucunu düzleştir"""
        if isinstance(result, list):
            flat = []
            for item in result:
                if isinstance(item, dict) and 'value' in item:
                    flat.append(item['value'])
                elif isinstance(item, str):
                    flat.append(item)
            return flat
        return []
    
    async def scrape_listing_detail(self, url: str) -> dict:
        """Tek bir ilanın detaylarını çek"""
        try:
            # curl_cffi ile hızlı fetch
            response = self.curl_session.get(url, timeout=30)
            
            if response.status_code != 200:
                return {'url': url, 'error': f'HTTP {response.status_code}'}
            
            html = response.text
            
            # HTML'den veri parse et
            import re
            
            data = {'url': url}
            
            # Başlık
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            data['title'] = title_match.group(1).strip() if title_match else None
            
            # İlan No
            id_match = re.search(r'İlan No[^0-9]*([0-9]+)', html)
            data['id'] = id_match.group(1) if id_match else None
            
            # Fiyat
            price_match = re.search(r'([0-9.,]+)\s*TL', html)
            data['price'] = price_match.group(0) if price_match else None
            
            # Açıklama
            desc_match = re.search(r'id="classifiedDescription"[^>]*>(.*?)</div>', html, re.DOTALL)
            if desc_match:
                desc = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
                data['description'] = ' '.join(desc.split())[:2000]
            
            # Fotoğraflar
            img_matches = re.findall(r'"(https://[^"]*\.sahibinden\.com/photos/[^"]+)"', html)
            data['images'] = list(set(img_matches))
            data['image_count'] = len(data['images'])
            
            # Özellikler tablosu
            specs = {}
            spec_matches = re.findall(r'<li[^>]*>\s*<strong>([^<]+)</strong>\s*<span>([^<]+)</span>', html)
            for label, value in spec_matches:
                specs[label.strip()] = value.strip()
            data['specifications'] = specs
            
            # Konum
            loc_match = re.search(r'<h2[^>]*>([^<]+)</h2>', html)
            data['location'] = loc_match.group(1).strip() if loc_match else None
            
            # Koordinatlar
            lat_match = re.search(r'"latitude":\s*([0-9.]+)', html)
            lng_match = re.search(r'"longitude":\s*([0-9.]+)', html)
            if lat_match and lng_match:
                data['coordinates'] = {
                    'lat': float(lat_match.group(1)),
                    'lng': float(lng_match.group(1))
                }
            
            return data
            
        except Exception as e:
            return {'url': url, 'error': str(e)}
    
    async def scrape_all_listings(self, urls: list, save_interval: int = 10) -> list:
        """Tüm ilanları scrape et"""
        print(f"\n📊 {len(urls)} ilan scrape edilecek...")
        
        DATA_DIR.mkdir(exist_ok=True)
        results = []
        
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {url[:60]}...", end=" ")
            
            data = await self.scrape_listing_detail(url)
            results.append(data)
            
            if data.get('error'):
                print(f"❌ {data['error']}")
            else:
                print(f"✓ {data.get('title', 'N/A')[:30]}... | 📷 {data.get('image_count', 0)}")
            
            # Periyodik kaydet
            if i % save_interval == 0:
                self._save_results(results)
                print(f"   💾 İlerleme kaydedildi ({i} ilan)")
            
            # Rate limiting
            await asyncio.sleep(1)
        
        # Final kaydet
        self._save_results(results)
        return results
    
    def _save_results(self, results: list):
        """Sonuçları kaydet"""
        output_file = DATA_DIR / "listings_detailed.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    
    async def download_images(self, results: list):
        """Tüm ilanların fotoğraflarını indir"""
        img_dir = DATA_DIR / "images"
        img_dir.mkdir(exist_ok=True)
        
        total_images = sum(len(r.get('images', [])) for r in results)
        print(f"\n📷 {total_images} fotoğraf indirilecek...")
        
        downloaded = 0
        for listing in results:
            listing_id = listing.get('id', 'unknown')
            images = listing.get('images', [])
            
            for idx, img_url in enumerate(images):
                try:
                    response = self.curl_session.get(img_url, timeout=30)
                    if response.status_code == 200:
                        ext = img_url.split('.')[-1].split('?')[0][:4]
                        filename = f"{listing_id}_{idx+1}.{ext}"
                        filepath = img_dir / filename
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        
                        downloaded += 1
                        
                except Exception as e:
                    pass
            
            if images:
                print(f"   ✓ İlan {listing_id}: {len(images)} fotoğraf")
        
        print(f"\n✅ {downloaded}/{total_images} fotoğraf indirildi → {img_dir}")
    
    async def close(self):
        """Temizlik"""
        if self.browser:
            await self.browser.stop()


async def main():
    scraper = SahibindenAuthenticatedScraper()
    
    try:
        await scraper.start()
        
        # Keller Williams Karma mağazası
        store_url = "https://kellerwillamskarma.sahibinden.com"
        
        # İlan URL'lerini topla
        urls = await scraper.get_store_listings(store_url, max_pages=10)
        
        if urls:
            # URL'leri kaydet
            urls_file = DATA_DIR / "listing_urls.json"
            DATA_DIR.mkdir(exist_ok=True)
            with open(urls_file, 'w') as f:
                json.dump(urls, f, indent=2)
            print(f"💾 URL'ler kaydedildi: {urls_file}")
            
            # Detayları scrape et
            results = await scraper.scrape_all_listings(urls)
            
            # Fotoğrafları indir
            download = input("\n📷 Fotoğrafları indirmek ister misiniz? (e/h): ")
            if download.lower() == 'e':
                await scraper.download_images(results)
            
            # Özet
            print("\n" + "=" * 60)
            print("📊 SONUÇ ÖZETİ")
            print("=" * 60)
            print(f"Toplam ilan: {len(results)}")
            print(f"Başarılı: {len([r for r in results if not r.get('error')])}")
            print(f"Hatalı: {len([r for r in results if r.get('error')])}")
            print(f"Toplam fotoğraf: {sum(len(r.get('images', [])) for r in results)}")
            print(f"\nVeriler: {DATA_DIR}")
        
    finally:
        await scraper.close()


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
