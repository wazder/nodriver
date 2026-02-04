# coding: utf-8
"""
Sahibinden.com Emlak Scraper - Hibrit Yaklaşım
nodriver + curl_cffi kullanarak optimize edilmiş scraping

nodriver: Anti-bot bypass, session/cookie yönetimi
curl_cffi: Hızlı API istekleri, paralel veri çekme
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlencode, parse_qs, urlparse

try:
    import nodriver as uc
except (ModuleNotFoundError, ImportError):
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import nodriver as uc

# curl_cffi - browser fingerprint'lerini taklit eden HTTP client
try:
    from curl_cffi.requests import AsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("⚠️  curl_cffi yüklü değil. Yüklemek için: pip install curl_cffi")
    print("   Sadece nodriver ile devam edilecek.\n")


class SahibindenSession:
    """
    Sahibinden.com için session yönetimi.
    nodriver ile cookie alır, curl_cffi ile hızlı istekler yapar.
    """
    
    BASE_URL = "https://www.sahibinden.com"
    
    # Emlak kategorileri
    EMLAK_CATEGORIES = {
        "satilik-daire": "/satilik-daire",
        "kiralik-daire": "/kiralik-daire",
        "satilik-residence": "/satilik-residence",
        "kiralik-residence": "/kiralik-residence",
        "satilik-villa": "/satilik-villa",
        "kiralik-villa": "/kiralik-villa",
        "satilik-mustakil-ev": "/satilik-mustakil-ev",
        "satilik-arsa": "/satilik-arsa",
        "gunluk-kiralik": "/gunluk-kiralik",
        "devren-satilik": "/devren-satilik-dukkan-magaza",
    }
    
    # Popüler şehirler
    CITIES = {
        "istanbul": "34",
        "ankara": "6", 
        "izmir": "35",
        "antalya": "7",
        "bursa": "16",
        "mugla": "48",
        "aydin": "9",
    }
    
    def __init__(self):
        self.cookies: dict = {}
        self.headers: dict = {}
        self.browser = None
        self.curl_session: Optional[AsyncSession] = None
        self._initialized = False
    
    async def initialize(self, headless: bool = False):
        """
        Browser'ı başlat ve gerekli cookie'leri al.
        """
        print("🚀 Browser başlatılıyor...")
        
        self.browser = await uc.start(
            headless=headless,
            lang="tr-TR",
            browser_args=[
                "--no-sandbox",
                "--disable-gpu",
            ],
        )
        
        tab = self.browser.main_tab
        
        # Sahibinden'e git ve cookie'leri al
        print("🌐 Sahibinden.com'a bağlanılıyor...")
        await tab.get(self.BASE_URL)
        await tab.wait(3)
        
        # Çerez popup'ını kapat
        await self._handle_cookie_popup(tab)
        
        # Cookie'leri al
        await self._extract_cookies(tab)
        
        # curl_cffi session'ı oluştur
        if CURL_CFFI_AVAILABLE:
            await self._setup_curl_session()
        
        self._initialized = True
        print("✅ Session hazır!")
        
        return tab
    
    async def _handle_cookie_popup(self, tab):
        """Çerez kabul popup'ını kapat."""
        try:
            # Farklı buton metinlerini dene
            for text in ["Kabul Et", "Tümünü Kabul Et", "Kabul"]:
                try:
                    btn = await tab.find(text, best_match=True)
                    if btn:
                        await btn.click()
                        await tab.wait(1)
                        print("🍪 Çerez popup'ı kapatıldı")
                        return
                except:
                    continue
        except Exception as e:
            pass  # Popup yoksa devam et
    
    async def _extract_cookies(self, tab):
        """Browser'dan cookie'leri çıkar."""
        try:
            print("   Cookie'ler alınıyor...")
            # CDP üzerinden cookie'leri al
            cookies_response = await tab.send(uc.cdp.network.get_cookies())
            
            for cookie in cookies_response:
                self.cookies[cookie.name] = cookie.value
            
            print(f"🍪 {len(self.cookies)} cookie alındı")
            
            # Önemli header'ları ayarla
            print("   User-Agent alınıyor...")
            user_agent = await tab.evaluate("navigator.userAgent")
            
            self.headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
            }
            print("   Headers ayarlandı")
            
        except Exception as e:
            print(f"⚠️ Cookie alma hatası: {e}")
            import traceback
            traceback.print_exc()
    
    async def _setup_curl_session(self):
        """curl_cffi async session oluştur."""
        self.curl_session = AsyncSession(
            impersonate="chrome120",  # Chrome 120 fingerprint'i
            cookies=self.cookies,
            headers=self.headers,
            timeout=30,
        )
        print("⚡ curl_cffi session hazır")
    
    async def fetch_with_curl(self, url: str) -> Optional[str]:
        """
        curl_cffi ile sayfa içeriğini çek.
        Başarısız olursa None döner.
        """
        if not CURL_CFFI_AVAILABLE or not self.curl_session:
            return None
        
        try:
            response = await self.curl_session.get(url)
            if response.status_code == 200:
                return response.text
            else:
                print(f"⚠️ HTTP {response.status_code}: {url}")
                return None
        except Exception as e:
            print(f"⚠️ curl_cffi hatası: {e}")
            return None
    
    async def fetch_with_browser(self, tab, url: str) -> str:
        """
        nodriver ile sayfa içeriğini çek.
        Anti-bot koruması için fallback.
        """
        await tab.get(url)
        await tab.wait(2)
        return await tab.get_content()
    
    async def close(self):
        """Session'ları kapat."""
        if self.curl_session:
            await self.curl_session.close()
        if self.browser:
            self.browser.stop()
        print("👋 Session kapatıldı")


class EmlakScraper:
    """
    Sahibinden.com Emlak İlanları Scraper
    """
    
    def __init__(self, session: SahibindenSession):
        self.session = session
        self.results: list[dict] = []
    
    async def scrape_listing_page(self, tab, url: str) -> list[dict]:
        """
        Bir liste sayfasındaki tüm emlak ilanlarını çeker.
        Önce curl_cffi dener, başarısız olursa browser kullanır.
        """
        html_content = None
        
        # Önce curl_cffi ile dene (daha hızlı)
        if CURL_CFFI_AVAILABLE:
            print(f"⚡ curl_cffi ile çekiliyor: {url[:60]}...")
            html_content = await self.session.fetch_with_curl(url)
        
        # curl_cffi başarısız olduysa browser kullan
        if not html_content:
            print(f"🌐 Browser ile çekiliyor: {url[:60]}...")
            await tab.get(url)
            await tab.wait(2)
            return await self._parse_listing_page_browser(tab)
        
        # HTML'i parse et
        return self._parse_listing_page_html(html_content)
    
    def _parse_listing_page_html(self, html: str) -> list[dict]:
        """
        HTML içeriğinden ilan listesini parse et.
        curl_cffi ile alınan içerik için.
        """
        listings = []
        
        # Basit regex ile ilan bilgilerini çek
        # Not: Gerçek projede BeautifulSoup veya lxml kullanılmalı
        
        # İlan ID'lerini bul
        pattern = r'data-id="(\d+)"[^>]*>.*?classifiedTitle[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for match in matches:
            listing_id, url, title = match
            listings.append({
                "id": listing_id,
                "url": url.strip(),
                "title": title.strip(),
            })
        
        # Fiyatları çek
        price_pattern = r'searchResultsPriceValue[^>]*>([^<]+)<'
        prices = re.findall(price_pattern, html)
        
        # Konumları çek  
        location_pattern = r'searchResultsLocationValue[^>]*>([^<]+)<'
        locations = re.findall(location_pattern, html)
        
        # Tarihleri çek
        date_pattern = r'searchResultsDateValue[^>]*>([^<]+)<'
        dates = re.findall(date_pattern, html)
        
        # Bilgileri birleştir
        for i, listing in enumerate(listings):
            if i < len(prices):
                listing["price"] = prices[i].strip()
            if i < len(locations):
                listing["location"] = locations[i].strip()
            if i < len(dates):
                listing["date"] = dates[i].strip()
        
        print(f"📋 {len(listings)} ilan parse edildi (curl_cffi)")
        return listings
    
    async def _parse_listing_page_browser(self, tab) -> list[dict]:
        """
        Browser üzerinden ilan listesini parse et.
        nodriver ile alınan içerik için.
        """
        listings = []
        
        # İlan satırlarını bul
        cards = await tab.select_all("tr.searchResultsItem")
        
        if not cards:
            # Alternatif: Büyük thumbnail görünümü
            cards = await tab.select_all(".searchResultsLargeThumbnail tbody tr")
        
        print(f"📋 {len(cards)} ilan kartı bulundu (browser)")
        
        for card in cards:
            try:
                listing = await self._parse_single_card(card)
                if listing.get("title"):
                    listings.append(listing)
            except Exception as e:
                continue
        
        return listings
    
    async def _parse_single_card(self, card) -> dict:
        """Tek bir ilan kartını parse et."""
        listing = {}
        
        try:
            # İlan ID
            listing["id"] = await card.get_attribute("data-id") or ""
            
            # Başlık ve URL
            title_elem = await card.query_selector("a.classifiedTitle")
            if title_elem:
                listing["title"] = title_elem.text.strip() if title_elem.text else ""
                listing["url"] = await title_elem.get_attribute("href") or ""
            
            # Fiyat
            price_elem = await card.query_selector("td.searchResultsPriceValue")
            if price_elem:
                listing["price"] = price_elem.text.strip() if price_elem.text else ""
            
            # Konum
            loc_elem = await card.query_selector("td.searchResultsLocationValue")
            if loc_elem:
                listing["location"] = loc_elem.text.strip() if loc_elem.text else ""
            
            # Tarih
            date_elem = await card.query_selector("td.searchResultsDateValue")
            if date_elem:
                listing["date"] = date_elem.text.strip() if date_elem.text else ""
            
            # Emlak özellikleri (m2, oda sayısı vs.)
            attr_elems = await card.query_selector_all("td.searchResultsAttributeValue")
            listing["attributes"] = []
            for attr in attr_elems:
                if attr.text:
                    listing["attributes"].append(attr.text.strip())
            
        except Exception as e:
            pass
        
        return listing
    
    async def scrape_listing_detail(self, tab, url: str) -> dict:
        """
        Tek bir ilanın detay sayfasını çeker.
        Emlak ilanları için özelleştirilmiş.
        """
        full_url = url if url.startswith("http") else f"{self.session.BASE_URL}{url}"
        
        # Önce curl_cffi ile dene
        html_content = None
        if CURL_CFFI_AVAILABLE:
            html_content = await self.session.fetch_with_curl(full_url)
        
        if html_content:
            return self._parse_detail_html(html_content, full_url)
        
        # Browser ile çek
        await tab.get(full_url)
        await tab.wait(2)
        return await self._parse_detail_browser(tab, full_url)
    
    def _parse_detail_html(self, html: str, url: str) -> dict:
        """HTML'den detay bilgilerini parse et."""
        detail = {"url": url}
        
        # Başlık
        title_match = re.search(r'classifiedDetailTitle[^>]*>([^<]+)<', html)
        if title_match:
            detail["title"] = title_match.group(1).strip()
        
        # Fiyat
        price_match = re.search(r'classifiedInfo[^>]*>.*?<h3>([^<]+)</h3>', html, re.DOTALL)
        if price_match:
            detail["price"] = price_match.group(1).strip()
        
        # İlan No
        id_match = re.search(r'İlan No[^<]*</strong>\s*<span>(\d+)</span>', html)
        if id_match:
            detail["listing_id"] = id_match.group(1)
        
        # Açıklama
        desc_match = re.search(r'id="classifiedDescription"[^>]*>(.*?)</div>', html, re.DOTALL)
        if desc_match:
            # HTML tag'lerini temizle
            desc = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
            detail["description"] = ' '.join(desc.split()).strip()
        
        return detail
    
    async def _parse_detail_browser(self, tab, url: str) -> dict:
        """Browser üzerinden detay bilgilerini parse et."""
        detail = {"url": url}
        
        try:
            # Başlık
            title = await tab.select("h1.classifiedDetailTitle")
            if title:
                detail["title"] = title.text.strip() if title.text else ""
            
            # Fiyat
            price = await tab.select(".classifiedInfo h3")
            if price:
                detail["price"] = price.text.strip() if price.text else ""
            
            # Açıklama
            description = await tab.select("#classifiedDescription")
            if description:
                detail["description"] = description.text.strip() if description.text else ""
            
            # Emlak özellikleri (m2, oda sayısı, kat vs.)
            detail["specs"] = {}
            spec_rows = await tab.select_all(".classifiedInfoList li")
            for row in spec_rows:
                try:
                    label = await row.query_selector("strong")
                    value = await row.query_selector("span")
                    if label and value:
                        key = label.text.strip() if label.text else ""
                        val = value.text.strip() if value.text else ""
                        if key:
                            detail["specs"][key] = val
                except:
                    continue
            
            # Harita koordinatları (varsa)
            try:
                map_elem = await tab.select("#gmap")
                if map_elem:
                    lat = await map_elem.get_attribute("data-lat")
                    lng = await map_elem.get_attribute("data-lng")
                    if lat and lng:
                        detail["coordinates"] = {"lat": lat, "lng": lng}
            except:
                pass
            
            # Resimler
            detail["images"] = []
            img_elements = await tab.select_all(".classifiedDetailMainPhoto img, .detail-slider img")
            for img in img_elements:
                src = await img.get_attribute("src") or await img.get_attribute("data-src")
                if src and "placeholder" not in src:
                    detail["images"].append(src)
            
            # İlan sahibi
            seller = await tab.select(".username-info-area a")
            if seller:
                detail["seller"] = seller.text.strip() if seller.text else ""
                detail["seller_url"] = await seller.get_attribute("href") or ""
            
        except Exception as e:
            print(f"⚠️ Detay parse hatası: {e}")
        
        return detail
    
    async def scrape_multiple_pages(self, tab, base_url: str, max_pages: int = 5) -> list[dict]:
        """
        Birden fazla sayfa çeker.
        Pagination destekli.
        """
        all_listings = []
        
        for page in range(1, max_pages + 1):
            # Sayfa URL'sini oluştur
            if "?" in base_url:
                page_url = f"{base_url}&pagingOffset={(page-1)*50}"
            else:
                page_url = f"{base_url}?pagingOffset={(page-1)*50}"
            
            print(f"\n📄 Sayfa {page}/{max_pages} çekiliyor...")
            
            listings = await self.scrape_listing_page(tab, page_url)
            
            if not listings:
                print(f"⚠️ Sayfa {page}'de ilan bulunamadı, durduruluyor.")
                break
            
            all_listings.extend(listings)
            print(f"   Toplam: {len(all_listings)} ilan")
            
            # Rate limiting - çok hızlı istek atmayalım
            await asyncio.sleep(1)
        
        return all_listings
    
    async def search_emlak(
        self,
        tab,
        category: str = "satilik-daire",
        city: str = None,
        min_price: int = None,
        max_price: int = None,
        min_m2: int = None,
        max_m2: int = None,
        room_count: str = None,  # "1+1", "2+1", "3+1" vs.
    ) -> str:
        """
        Filtreli emlak araması için URL oluşturur.
        """
        base_path = self.session.EMLAK_CATEGORIES.get(category, "/satilik-daire")
        url = f"{self.session.BASE_URL}{base_path}"
        
        params = {}
        
        # Şehir filtresi
        if city and city.lower() in self.session.CITIES:
            # Şehir URL'ye eklenir
            url = f"{url}/{city.lower()}"
        
        # Fiyat filtresi
        if min_price:
            params["price_min"] = min_price
        if max_price:
            params["price_max"] = max_price
        
        # m2 filtresi
        if min_m2:
            params["a24_min"] = min_m2
        if max_m2:
            params["a24_max"] = max_m2
        
        # Oda sayısı
        if room_count:
            room_mapping = {
                "1+0": "a81",
                "1+1": "a82", 
                "2+1": "a83",
                "3+1": "a84",
                "4+1": "a85",
                "5+1": "a86",
            }
            if room_count in room_mapping:
                params[room_mapping[room_count]] = "true"
        
        if params:
            url = f"{url}?{urlencode(params)}"
        
        return url


async def main():
    """
    Ana fonksiyon - Emlak scraping örneği
    """
    print("=" * 60)
    print("🏠 Sahibinden.com Emlak Scraper")
    print("   nodriver + curl_cffi hibrit sistem")
    print("=" * 60)
    
    # Session başlat
    session = SahibindenSession()
    
    try:
        # Browser'ı başlat ve cookie'leri al
        tab = await session.initialize(headless=False)
        
        # Scraper oluştur
        scraper = EmlakScraper(session)
        
        # ═══════════════════════════════════════════════════════════
        # ÖRNEK 1: Satılık daire ilanlarını çek
        # ═══════════════════════════════════════════════════════════
        print("\n" + "─" * 50)
        print("📋 Örnek 1: Satılık Daire İlanları")
        print("─" * 50)
        
        url = f"{session.BASE_URL}/satilik-daire/istanbul"
        listings = await scraper.scrape_listing_page(tab, url)
        
        print(f"\n✅ {len(listings)} ilan bulundu!")
        
        # İlk 5 ilanı göster
        for i, listing in enumerate(listings[:5], 1):
            print(f"\n  [{i}] {listing.get('title', 'N/A')[:50]}...")
            print(f"      💰 {listing.get('price', 'N/A')}")
            print(f"      📍 {listing.get('location', 'N/A')}")
            if listing.get('attributes'):
                print(f"      📐 {' | '.join(listing['attributes'][:3])}")
        
        # ═══════════════════════════════════════════════════════════
        # ÖRNEK 2: Filtreli arama
        # ═══════════════════════════════════════════════════════════
        print("\n" + "─" * 50)
        print("🔍 Örnek 2: Filtreli Arama (Kiralık 2+1, İstanbul)")
        print("─" * 50)
        
        search_url = await scraper.search_emlak(
            tab,
            category="kiralik-daire",
            city="istanbul",
            min_price=10000,
            max_price=30000,
            room_count="2+1",
        )
        print(f"   URL: {search_url}")
        
        filtered_listings = await scraper.scrape_listing_page(tab, search_url)
        print(f"\n✅ {len(filtered_listings)} ilan bulundu!")
        
        for i, listing in enumerate(filtered_listings[:3], 1):
            print(f"\n  [{i}] {listing.get('title', 'N/A')[:50]}...")
            print(f"      💰 {listing.get('price', 'N/A')}")
        
        # ═══════════════════════════════════════════════════════════
        # ÖRNEK 3: Çoklu sayfa çekme
        # ═══════════════════════════════════════════════════════════
        # print("\n" + "─" * 50)
        # print("📚 Örnek 3: Çoklu Sayfa (3 sayfa)")
        # print("─" * 50)
        # 
        # multi_page_url = f"{session.BASE_URL}/satilik-daire/istanbul"
        # all_listings = await scraper.scrape_multiple_pages(tab, multi_page_url, max_pages=3)
        # print(f"\n✅ Toplam {len(all_listings)} ilan çekildi!")
        
        # ═══════════════════════════════════════════════════════════
        # ÖRNEK 4: İlan detayı çekme
        # ═══════════════════════════════════════════════════════════
        if listings and listings[0].get('url'):
            print("\n" + "─" * 50)
            print("📄 Örnek 4: İlan Detayı")
            print("─" * 50)
            
            detail_url = listings[0]['url']
            detail = await scraper.scrape_listing_detail(tab, detail_url)
            
            print(f"\n  Başlık: {detail.get('title', 'N/A')}")
            print(f"  Fiyat: {detail.get('price', 'N/A')}")
            print(f"  Satıcı: {detail.get('seller', 'N/A')}")
            if detail.get('specs'):
                print("  Özellikler:")
                for k, v in list(detail['specs'].items())[:5]:
                    print(f"    - {k}: {v}")
            if detail.get('images'):
                print(f"  Resim sayısı: {len(detail['images'])}")
        
        # ═══════════════════════════════════════════════════════════
        # Sonuçları kaydet
        # ═══════════════════════════════════════════════════════════
        output_file = f"emlak_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "scrape_date": datetime.now().isoformat(),
                "total_listings": len(listings),
                "listings": listings,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Sonuçlar kaydedildi: {output_file}")
        
        # Sonuçları görmek için bekle
        print("\n⏳ 5 saniye bekleniyor...")
        await tab.wait(5)
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await session.close()


async def quick_scrape(url: str, max_pages: int = 1, headless: bool = True) -> list[dict]:
    """
    Hızlı scraping için yardımcı fonksiyon.
    
    Kullanım:
        results = await quick_scrape("https://www.sahibinden.com/satilik-daire/istanbul", max_pages=3)
    """
    session = SahibindenSession()
    
    try:
        tab = await session.initialize(headless=headless)
        scraper = EmlakScraper(session)
        
        if max_pages > 1:
            return await scraper.scrape_multiple_pages(tab, url, max_pages)
        else:
            return await scraper.scrape_listing_page(tab, url)
    
    finally:
        await session.close()


if __name__ == "__main__":
    # Ana loop'u çalıştır
    uc.loop().run_until_complete(main())
