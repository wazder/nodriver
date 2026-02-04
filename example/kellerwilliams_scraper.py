# coding: utf-8
"""
Keller Williams Karma - Sahibinden Mağaza Scraper
Tüm ilanların detaylı verilerini çeker (fotoğraflar, açıklamalar, özellikler)
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

try:
    import nodriver as uc
except (ModuleNotFoundError, ImportError):
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import nodriver as uc

# curl_cffi opsiyonel - hızlı indirme için
try:
    from curl_cffi.requests import AsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("⚠️  curl_cffi yüklü değil - sadece browser modu kullanılacak")


class KellerWilliamsScraper:
    """
    Keller Williams Karma mağazasındaki tüm ilanları detaylı çeker.
    """
    
    BASE_URL = "https://www.sahibinden.com"
    STORE_URL = "https://kellerwillamskarma.sahibinden.com"
    
    def __init__(self, output_dir: str = "kellerwilliams_data"):
        self.browser = None
        self.tab = None
        self.cookies = {}
        self.headers = {}
        self.curl_session = None
        self.output_dir = output_dir
        self.all_listings = []
        self.detailed_listings = []
        
        # Output klasörlerini oluştur
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)
    
    async def start(self, headless: bool = False):
        """Browser başlat."""
        print("🚀 Browser başlatılıyor...")
        self.browser = await uc.start(
            headless=headless,
            browser_args=["--no-sandbox", "--disable-gpu"],
        )
        self.tab = self.browser.main_tab
        
        # Önce ana sahibinden'e git (cookie almak için)
        print("🌐 Sahibinden.com'a bağlanılıyor...")
        await self.tab.get(self.BASE_URL)
        await self.tab.wait(3)
        
        # Çerez popup'ını kapat
        await self._handle_cookie_popup()
        
        # Session bilgilerini al
        await self._extract_session()
        
        # Şimdi mağaza sayfasına git
        print(f"🏪 Mağaza sayfasına gidiliyor: {self.STORE_URL}")
        await self.tab.get(self.STORE_URL)
        await self.tab.wait(3)
        
        print("✅ Scraper hazır!")
        return self
    
    async def _handle_cookie_popup(self):
        """Çerez popup'ını kapat."""
        try:
            for text in ["Kabul Et", "Tümünü Kabul Et", "Accept All"]:
                try:
                    btn = await self.tab.find(text, best_match=True)
                    if btn:
                        await btn.click()
                        print("🍪 Çerez popup'ı kapatıldı")
                        await self.tab.wait(1)
                        return
                except:
                    continue
        except:
            pass
    
    async def _extract_session(self):
        """Cookie ve header bilgilerini al."""
        try:
            user_agent = await self.tab.evaluate("navigator.userAgent")
            self.headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                "Referer": self.STORE_URL,
            }
            
            # Cookie'leri al
            try:
                cookies_str = await self.tab.evaluate("document.cookie")
                if cookies_str:
                    for cookie in cookies_str.split(";"):
                        if "=" in cookie:
                            name, value = cookie.strip().split("=", 1)
                            self.cookies[name] = value
                    print(f"🍪 {len(self.cookies)} cookie alındı")
            except:
                pass
            
            # curl_cffi session
            if CURL_CFFI_AVAILABLE and self.cookies:
                self.curl_session = AsyncSession(
                    impersonate="chrome120",
                    cookies=self.cookies,
                    headers=self.headers,
                    timeout=30,
                )
                print("⚡ curl_cffi aktif")
        except Exception as e:
            print(f"⚠️ Session hatası: {e}")
    
    async def get_all_listing_urls(self) -> list[str]:
        """
        Mağazadaki tüm ilan URL'lerini çek.
        Pagination ile tüm sayfaları dolaş.
        """
        all_urls = []
        page = 0
        
        while True:
            # Sayfa URL'si
            if page == 0:
                url = self.STORE_URL
            else:
                url = f"{self.STORE_URL}?pagingOffset={page * 50}"
            
            print(f"\n📄 Sayfa {page + 1} taranıyor: {url[:60]}...")
            await self.tab.get(url)
            await self.tab.wait(3)
            
            # Debug: Sayfadaki elementleri kontrol et
            debug_info = await self.tab.evaluate("""
            (() => {
                const info = {};
                info.url = window.location.href;
                info.title = document.title;
                
                // Farklı selector'ları dene
                info.searchResultsItem = document.querySelectorAll('tr.searchResultsItem').length;
                info.classifiedTitle = document.querySelectorAll('a.classifiedTitle').length;
                info.resultLinks = document.querySelectorAll('td.searchResultsTitleValue a').length;
                info.allLinks = document.querySelectorAll('a[href*="/ilan/"]').length;
                info.storeLinks = document.querySelectorAll('.classified-list a').length;
                info.tableRows = document.querySelectorAll('table tbody tr').length;
                
                // İlk link'i bul
                const firstLink = document.querySelector('a[href*="/ilan/"]');
                info.firstLinkHref = firstLink ? firstLink.getAttribute('href') : 'none';
                
                return info;
            })()
            """)
            
            print(f"   Debug: {debug_info}")
            
            # İlan URL'lerini çek - farklı selector'ları dene
            js_code = """
            (() => {
                const urls = [];
                
                // Method 1: tr.searchResultsItem içindeki linkler
                document.querySelectorAll('tr.searchResultsItem td a[href*="/ilan/"]').forEach(a => {
                    const href = a.getAttribute('href');
                    if (href && !urls.includes(href)) urls.push(href);
                });
                
                // Method 2: Tüm ilan linkleri
                if (urls.length === 0) {
                    document.querySelectorAll('a[href*="/ilan/"]').forEach(a => {
                        const href = a.getAttribute('href');
                        if (href && href.includes('/ilan/') && !urls.includes(href)) {
                            urls.push(href);
                        }
                    });
                }
                
                // Method 3: classifiedTitle class'ı
                if (urls.length === 0) {
                    document.querySelectorAll('a.classifiedTitle').forEach(a => {
                        const href = a.getAttribute('href');
                        if (href && !urls.includes(href)) urls.push(href);
                    });
                }
                
                return urls;
            })()
            """
            
            result = await self.tab.evaluate(js_code)
            
            # Sonuçları düzleştir
            urls = []
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict) and "value" in item:
                        urls.append(item["value"])
                    elif isinstance(item, str):
                        urls.append(item)
            
            if not urls:
                print(f"   ⚠️ Bu sayfada ilan bulunamadı, tarama tamamlandı.")
                break
            
            print(f"   ✓ {len(urls)} ilan URL'si bulundu")
            all_urls.extend(urls)
            
            # Sonraki sayfa var mı kontrol et
            has_next = await self.tab.evaluate("""
                (() => {
                    const next = document.querySelector('.pagingButtons .next:not(.disabled)') ||
                                 document.querySelector('a.next:not(.disabled)') ||
                                 document.querySelector('[class*="next"]:not(.disabled)');
                    return next !== null;
                })()
            """)
            
            has_next_val = has_next.get("value", False) if isinstance(has_next, dict) else has_next
            
            if not has_next_val:
                print(f"   ℹ️ Son sayfaya ulaşıldı.")
                break
            
            page += 1
            await asyncio.sleep(1)  # Rate limiting
        
        # Duplicate'leri kaldır
        unique_urls = list(dict.fromkeys(all_urls))
        print(f"\n📋 Toplam {len(unique_urls)} benzersiz ilan bulundu")
        
        return unique_urls
    
    async def scrape_listing_detail(self, url: str, index: int, total: int) -> dict:
        """
        Tek bir ilanın tüm detaylarını çek.
        """
        full_url = url if url.startswith("http") else f"{self.BASE_URL}{url}"
        
        print(f"\n[{index}/{total}] İlan çekiliyor: {full_url[:60]}...")
        
        await self.tab.get(full_url)
        await self.tab.wait(2)
        
        # JavaScript ile tüm verileri çek
        js_code = """
        (() => {
            const data = {};
            
            // İlan ID
            const urlMatch = window.location.pathname.match(/\\/ilan\\/(\\d+)/);
            data.id = urlMatch ? urlMatch[1] : '';
            data.url = window.location.href;
            
            // Başlık
            const titleEl = document.querySelector('h1.classifiedDetailTitle');
            data.title = titleEl ? titleEl.innerText.trim() : '';
            
            // Fiyat
            const priceEl = document.querySelector('.classifiedInfo h3');
            data.price = priceEl ? priceEl.innerText.trim() : '';
            
            // Alternatif fiyat alanı
            if (!data.price) {
                const altPrice = document.querySelector('.classified-price-wrapper .price');
                data.price = altPrice ? altPrice.innerText.trim() : '';
            }
            
            // Açıklama
            const descEl = document.querySelector('#classifiedDescription');
            data.description = descEl ? descEl.innerText.trim() : '';
            
            // Özellikler tablosu (ana bilgiler)
            data.specs = {};
            const infoList = document.querySelectorAll('.classifiedInfoList li');
            infoList.forEach(li => {
                const strong = li.querySelector('strong');
                const span = li.querySelector('span');
                if (strong && span) {
                    const key = strong.innerText.replace(':', '').trim();
                    const value = span.innerText.trim();
                    if (key) data.specs[key] = value;
                }
            });
            
            // Detay özellikleri (ilan detayları tablosu)
            data.details = {};
            const detailRows = document.querySelectorAll('.classified-detail-info-list li, .uiBox .props li');
            detailRows.forEach(row => {
                const label = row.querySelector('strong, .label');
                const value = row.querySelector('span, .value');
                if (label && value) {
                    const key = label.innerText.replace(':', '').trim();
                    const val = value.innerText.trim();
                    if (key && val) data.details[key] = val;
                }
            });
            
            // Harita koordinatları
            const mapEl = document.querySelector('#gmap, [data-lat], [data-lng]');
            if (mapEl) {
                data.coordinates = {
                    lat: mapEl.getAttribute('data-lat') || '',
                    lng: mapEl.getAttribute('data-lng') || ''
                };
            }
            
            // Tüm fotoğraflar
            data.images = [];
            
            // Büyük fotoğraflar (galeri)
            const galleryImgs = document.querySelectorAll('.classifiedDetailMainPhoto img, .galleryBig img');
            galleryImgs.forEach(img => {
                const src = img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-original');
                if (src && !src.includes('placeholder') && !data.images.includes(src)) {
                    data.images.push(src);
                }
            });
            
            // Thumbnail'lerden büyük URL'leri çıkar
            const thumbs = document.querySelectorAll('.classifiedDetailThumbList img, .thumbs img, .gallery-thumbs img');
            thumbs.forEach(img => {
                let src = img.getAttribute('src') || img.getAttribute('data-src');
                if (src) {
                    // Thumbnail'i büyük versiyona çevir
                    src = src.replace('_tbase.', '_x.').replace('_s.', '_x.').replace('_m.', '_x.');
                    if (!src.includes('placeholder') && !data.images.includes(src)) {
                        data.images.push(src);
                    }
                }
            });
            
            // data-img-src attribute'larından da çek
            const imgDataEls = document.querySelectorAll('[data-img-src]');
            imgDataEls.forEach(el => {
                let src = el.getAttribute('data-img-src');
                if (src) {
                    src = src.replace('_tbase.', '_x.').replace('_s.', '_x.').replace('_m.', '_x.');
                    if (!src.includes('placeholder') && !data.images.includes(src)) {
                        data.images.push(src);
                    }
                }
            });
            
            // İlan sahibi bilgileri
            data.seller = {};
            const sellerName = document.querySelector('.username-info-area a, .store-name a');
            if (sellerName) {
                data.seller.name = sellerName.innerText.trim();
                data.seller.url = sellerName.getAttribute('href') || '';
            }
            
            const sellerPhone = document.querySelector('.phone-number, .classified-phone');
            if (sellerPhone) {
                data.seller.phone = sellerPhone.innerText.trim();
            }
            
            // İlan tarihi
            const dateEl = document.querySelector('.classified-date-info, .update-date');
            data.date = dateEl ? dateEl.innerText.trim() : '';
            
            // İlan no
            const ilanNo = document.querySelector('.classified-no');
            if (ilanNo) {
                data.listing_no = ilanNo.innerText.replace('İlan No:', '').trim();
            }
            
            // Konum bilgisi
            data.location = {};
            const locEls = document.querySelectorAll('.classified-location a, .region a');
            locEls.forEach((el, i) => {
                const text = el.innerText.trim();
                if (i === 0) data.location.city = text;
                else if (i === 1) data.location.district = text;
                else if (i === 2) data.location.neighborhood = text;
            });
            
            // Breadcrumb'dan kategori bilgisi
            data.category = [];
            const breadcrumbs = document.querySelectorAll('.breadcrumb a, .categoriesContainer a');
            breadcrumbs.forEach(a => {
                const text = a.innerText.trim();
                if (text && text !== 'Sahibinden' && text !== 'Ana Sayfa') {
                    data.category.push(text);
                }
            });
            
            return data;
        })()
        """
        
        try:
            result = await self.tab.evaluate(js_code)
            
            # Nested yapıyı düzleştir
            listing = self._flatten_result(result)
            
            # Özet göster
            title = listing.get('title', '')[:50] or f"İlan #{listing.get('id', 'N/A')}"
            price = listing.get('price', 'N/A')
            img_count = len(listing.get('images', []))
            print(f"   ✓ {title}...")
            print(f"      💰 {price} | 📷 {img_count} fotoğraf")
            
            return listing
            
        except Exception as e:
            print(f"   ❌ Hata: {e}")
            return {"url": full_url, "error": str(e)}
    
    def _flatten_result(self, result) -> dict:
        """Nested JS sonucunu düzleştir."""
        if not isinstance(result, dict):
            return {}
        
        flat = {}
        
        def extract_value(obj):
            if isinstance(obj, dict):
                if "value" in obj:
                    val = obj["value"]
                    if isinstance(val, list):
                        # Array içindeki değerleri çıkar
                        return [extract_value(item) for item in val]
                    elif isinstance(val, dict):
                        return extract_value(val)
                    return val
                else:
                    # Normal dict
                    return {k: extract_value(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [extract_value(item) for item in obj]
            return obj
        
        for key, value in result.items():
            if isinstance(value, dict) and "value" in value:
                flat[key] = extract_value(value)
            else:
                flat[key] = extract_value(value)
        
        return flat
    
    async def scrape_all_details(self, urls: list[str], save_interval: int = 10):
        """
        Tüm ilanların detaylarını çek.
        Her save_interval ilandan sonra kaydet.
        """
        total = len(urls)
        print(f"\n{'='*60}")
        print(f"📊 {total} ilanın detayları çekilecek")
        print(f"{'='*60}")
        
        for i, url in enumerate(urls, 1):
            try:
                listing = await self.scrape_listing_detail(url, i, total)
                self.detailed_listings.append(listing)
                
                # Ara kayıt
                if i % save_interval == 0:
                    self._save_progress()
                
                # Rate limiting
                await asyncio.sleep(1.5)
                
            except Exception as e:
                print(f"   ❌ İlan {i} atlandı: {e}")
                self.detailed_listings.append({"url": url, "error": str(e)})
                continue
        
        # Final kayıt
        self._save_progress()
        
        return self.detailed_listings
    
    def _save_progress(self):
        """Mevcut ilerlemeyi kaydet."""
        output_file = os.path.join(self.output_dir, "listings_detailed.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "scrape_date": datetime.now().isoformat(),
                "store_url": self.STORE_URL,
                "total_listings": len(self.detailed_listings),
                "listings": self.detailed_listings,
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 İlerleme kaydedildi: {output_file} ({len(self.detailed_listings)} ilan)")
    
    async def download_images(self, max_concurrent: int = 5):
        """
        Tüm fotoğrafları indir.
        """
        if not CURL_CFFI_AVAILABLE:
            print("⚠️ Fotoğraf indirme için curl_cffi gerekli")
            return
        
        print(f"\n{'='*60}")
        print("📷 Fotoğraflar indiriliyor...")
        print(f"{'='*60}")
        
        images_dir = os.path.join(self.output_dir, "images")
        
        # Tüm fotoğraf URL'lerini topla
        all_images = []
        for listing in self.detailed_listings:
            listing_id = listing.get('id', 'unknown')
            for i, img_url in enumerate(listing.get('images', [])):
                all_images.append({
                    'url': img_url,
                    'listing_id': listing_id,
                    'index': i,
                })
        
        print(f"📷 Toplam {len(all_images)} fotoğraf indirilecek")
        
        # Semaphore ile concurrent indirme
        sem = asyncio.Semaphore(max_concurrent)
        downloaded = 0
        failed = 0
        
        async def download_one(img_info):
            nonlocal downloaded, failed
            async with sem:
                try:
                    url = img_info['url']
                    listing_id = img_info['listing_id']
                    idx = img_info['index']
                    
                    # Dosya adı
                    ext = url.split('.')[-1].split('?')[0]
                    if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                        ext = 'jpg'
                    filename = f"{listing_id}_{idx:02d}.{ext}"
                    filepath = os.path.join(images_dir, filename)
                    
                    # Zaten varsa atla
                    if os.path.exists(filepath):
                        downloaded += 1
                        return
                    
                    # İndir
                    response = await self.curl_session.get(url)
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        downloaded += 1
                    else:
                        failed += 1
                        
                except Exception as e:
                    failed += 1
        
        # Paralel indirme
        tasks = [download_one(img) for img in all_images]
        
        # Progress ile çalıştır
        batch_size = 50
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            await asyncio.gather(*batch)
            print(f"   İndirilen: {downloaded}/{len(all_images)} | Hatalı: {failed}")
        
        print(f"\n✅ Fotoğraf indirme tamamlandı: {downloaded} başarılı, {failed} hatalı")
    
    def create_summary(self):
        """Özet rapor oluştur."""
        summary_file = os.path.join(self.output_dir, "summary.txt")
        
        # İstatistikler
        total = len(self.detailed_listings)
        successful = len([l for l in self.detailed_listings if not l.get('error')])
        total_images = sum(len(l.get('images', [])) for l in self.detailed_listings)
        
        # Fiyat analizi
        prices = []
        for l in self.detailed_listings:
            price_str = l.get('price', '').replace('.', '').replace(' TL', '').replace('TL', '').strip()
            if price_str.isdigit():
                prices.append(int(price_str))
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("KELLER WILLIAMS KARMA - SCRAPING RAPORU\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Mağaza: {self.STORE_URL}\n\n")
            f.write(f"Toplam İlan: {total}\n")
            f.write(f"Başarılı: {successful}\n")
            f.write(f"Toplam Fotoğraf: {total_images}\n\n")
            
            if prices:
                f.write("FİYAT ANALİZİ:\n")
                f.write(f"  Minimum: {min(prices):,} TL\n")
                f.write(f"  Maksimum: {max(prices):,} TL\n")
                f.write(f"  Ortalama: {sum(prices)//len(prices):,} TL\n\n")
            
            f.write("DOSYALAR:\n")
            f.write(f"  listings_detailed.json - Tüm ilan detayları\n")
            f.write(f"  images/ - Fotoğraflar\n")
            f.write(f"  summary.txt - Bu rapor\n")
        
        print(f"\n📄 Özet rapor: {summary_file}")
    
    async def close(self):
        """Kaynakları temizle."""
        if self.curl_session:
            await self.curl_session.close()
        if self.browser:
            self.browser.stop()
        print("👋 Scraper kapatıldı.")


async def main():
    """
    Ana fonksiyon
    """
    print("=" * 60)
    print("🏠 KELLER WILLIAMS KARMA - DETAYLI SCRAPER")
    print("   Tüm ilanların tam verileri çekilecek")
    print("=" * 60)
    
    scraper = KellerWilliamsScraper(output_dir="kellerwilliams_data")
    
    try:
        # Başlat
        await scraper.start(headless=False)
        
        # 1. Tüm ilan URL'lerini çek
        print("\n" + "─" * 50)
        print("📋 ADIM 1: İlan URL'leri toplanıyor...")
        print("─" * 50)
        
        urls = await scraper.get_all_listing_urls()
        
        if not urls:
            print("❌ İlan bulunamadı!")
            return
        
        # URL'leri kaydet
        urls_file = os.path.join(scraper.output_dir, "listing_urls.json")
        with open(urls_file, 'w', encoding='utf-8') as f:
            json.dump(urls, f, ensure_ascii=False, indent=2)
        print(f"💾 URL'ler kaydedildi: {urls_file}")
        
        # 2. Tüm ilanların detaylarını çek
        print("\n" + "─" * 50)
        print("📄 ADIM 2: İlan detayları çekiliyor...")
        print("─" * 50)
        
        await scraper.scrape_all_details(urls, save_interval=10)
        
        # 3. Fotoğrafları indir (opsiyonel)
        print("\n" + "─" * 50)
        print("📷 ADIM 3: Fotoğraflar indiriliyor...")
        print("─" * 50)
        
        await scraper.download_images(max_concurrent=5)
        
        # 4. Özet rapor
        scraper.create_summary()
        
        # Sonuç
        print("\n" + "=" * 60)
        print("✅ SCRAPING TAMAMLANDI!")
        print(f"   📁 Veriler: {scraper.output_dir}/")
        print(f"   📊 Toplam: {len(scraper.detailed_listings)} ilan")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ İşlem kullanıcı tarafından durduruldu")
        scraper._save_progress()
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        scraper._save_progress()
        
    finally:
        await scraper.close()


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
