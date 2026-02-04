# coding: utf-8
"""
Sahibinden.com Emlak Scraper - Hibrit Versiyon
nodriver + curl_cffi ile optimize edilmiş
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Optional

try:
    import nodriver as uc
except (ModuleNotFoundError, ImportError):
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import nodriver as uc

# curl_cffi opsiyonel
try:
    from curl_cffi.requests import AsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("⚠️  curl_cffi yüklü değil. pip install curl_cffi ile yükleyebilirsiniz.")
    print("   Sadece nodriver ile devam edilecek (daha yavaş).\n")


# Emlak kategorileri
EMLAK_CATEGORIES = {
    "satilik-daire": "/satilik-daire",
    "kiralik-daire": "/kiralik-daire",
    "satilik-residence": "/satilik-residence",
    "satilik-villa": "/satilik-villa",
    "kiralik-villa": "/kiralik-villa",
    "satilik-arsa": "/satilik-arsa",
}


async def scrape_listing_page(tab, url: str) -> list[dict]:
    """
    Bir liste sayfasındaki tüm emlak ilanlarını çeker.
    """
    print(f"🌐 Sayfa yükleniyor: {url[:60]}...")
    await tab.get(url)
    await tab.wait(3)
    
    listings = []
    
    # İlan satırlarını bul - Sahibinden'in tablo yapısı
    cards = await tab.select_all("tr.searchResultsItem")
    
    if not cards:
        print("⚠️ searchResultsItem bulunamadı, alternatif selector deneniyor...")
        # Alternatif: tbody içindeki tr'ler
        cards = await tab.select_all("tbody.searchResultsRowClass tr")
    
    print(f"📋 {len(cards)} ilan kartı bulundu")
    
    for i, card in enumerate(cards):
        try:
            listing = {}
            
            # İlan ID
            try:
                listing["id"] = await card.get_attribute("data-id") or ""
            except:
                listing["id"] = ""
            
            # Başlık ve URL - td içindeki a.classifiedTitle
            try:
                title_elem = await card.query_selector("td.searchResultsTitleValue a")
                if title_elem:
                    # Text içeriğini al
                    title_text = await tab.evaluate(
                        f'document.querySelector("tr.searchResultsItem:nth-child({i+1}) td.searchResultsTitleValue a").innerText'
                    )
                    listing["title"] = title_text.strip() if title_text else ""
                    listing["url"] = await title_elem.get_attribute("href") or ""
            except Exception as e:
                print(f"   Başlık hatası: {e}")
            
            # Fiyat
            try:
                price_elem = await card.query_selector("td.searchResultsPriceValue")
                if price_elem:
                    price_text = await tab.evaluate(
                        f'document.querySelector("tr.searchResultsItem:nth-child({i+1}) td.searchResultsPriceValue").innerText'
                    )
                    listing["price"] = price_text.strip() if price_text else ""
            except:
                pass
            
            # Konum
            try:
                loc_elem = await card.query_selector("td.searchResultsLocationValue")
                if loc_elem:
                    loc_text = await tab.evaluate(
                        f'document.querySelector("tr.searchResultsItem:nth-child({i+1}) td.searchResultsLocationValue").innerText'
                    )
                    listing["location"] = loc_text.strip() if loc_text else ""
            except:
                pass
            
            # Tarih
            try:
                date_elem = await card.query_selector("td.searchResultsDateValue")
                if date_elem:
                    date_text = await tab.evaluate(
                        f'document.querySelector("tr.searchResultsItem:nth-child({i+1}) td.searchResultsDateValue").innerText'
                    )
                    listing["date"] = date_text.strip() if date_text else ""
            except:
                pass
            
            if listing.get("title") or listing.get("id"):
                listings.append(listing)
                
        except Exception as e:
            print(f"   Kart {i+1} hatası: {e}")
            continue
    
    return listings


async def scrape_with_js(tab, url: str) -> list[dict]:
    """
    JavaScript ile doğrudan DOM'dan veri çeker.
    Daha güvenilir yöntem.
    """
    print(f"🌐 Sayfa yükleniyor: {url[:60]}...")
    await tab.get(url)
    await tab.wait(3)
    
    # JavaScript ile tüm ilanları çek
    js_code = """
    (() => {
        const listings = [];
        const rows = document.querySelectorAll('tr.searchResultsItem');
        
        rows.forEach((row, index) => {
            try {
                const listing = {};
                
                // ID
                listing.id = row.getAttribute('data-id') || '';
                
                // Başlık ve URL - titleCell içindeki a tag'i
                const titleCell = row.querySelector('td.searchResultsTitleValue');
                if (titleCell) {
                    const titleLink = titleCell.querySelector('a');
                    if (titleLink) {
                        // Başlık: span içindeki text veya a'nın text'i
                        const titleSpan = titleLink.querySelector('span');
                        listing.title = titleSpan ? titleSpan.innerText.trim() : titleLink.innerText.trim();
                        listing.url = titleLink.getAttribute('href') || '';
                    }
                }
                
                // Fiyat
                const priceEl = row.querySelector('td.searchResultsPriceValue');
                if (priceEl) {
                    listing.price = priceEl.innerText.trim();
                }
                
                // Konum
                const locEl = row.querySelector('td.searchResultsLocationValue');
                if (locEl) {
                    listing.location = locEl.innerText.replace(/\\n/g, ' ').trim();
                }
                
                // Tarih
                const dateEl = row.querySelector('td.searchResultsDateValue');
                if (dateEl) {
                    listing.date = dateEl.innerText.replace(/\\n/g, ' ').trim();
                }
                
                // Özellikler (m2, oda sayısı vs.)
                const attrEls = row.querySelectorAll('td.searchResultsAttributeValue');
                listing.m2 = attrEls[0] ? attrEls[0].innerText.trim() : '';
                listing.room = attrEls[1] ? attrEls[1].innerText.trim() : '';
                
                // Resim
                const imgEl = row.querySelector('img');
                if (imgEl) {
                    listing.image = imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '';
                }
                
                if (listing.id) {
                    listings.push(listing);
                }
            } catch (e) {
                console.error('Row parse error:', e);
            }
        });
        
        return listings;
    })()
    """
    
    try:
        result = await tab.evaluate(js_code)
        
        # nodriver bazen nested object döner, düzleştir
        listings = []
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    # Nested "value" yapısını düzleştir
                    flat = {}
                    if "value" in item and isinstance(item["value"], list):
                        for pair in item["value"]:
                            if isinstance(pair, list) and len(pair) == 2:
                                key = pair[0]
                                val_obj = pair[1]
                                if isinstance(val_obj, dict) and "value" in val_obj:
                                    flat[key] = val_obj["value"]
                                else:
                                    flat[key] = val_obj
                        listings.append(flat)
                    else:
                        listings.append(item)
                else:
                    listings.append(item)
        
        print(f"📋 {len(listings)} ilan çekildi")
        return listings
    except Exception as e:
        print(f"⚠️ JS hatası: {e}")
        import traceback
        traceback.print_exc()
        return []


def parse_html_listings(html: str) -> list[dict]:
    """
    HTML'den ilan bilgilerini regex ile çeker.
    curl_cffi ile alınan içerik için.
    """
    listings = []
    
    # Her bir ilan satırını bul
    row_pattern = r'<tr[^>]*class="[^"]*searchResultsItem[^"]*"[^>]*data-id="(\d+)"[^>]*>(.*?)</tr>'
    rows = re.findall(row_pattern, html, re.DOTALL)
    
    for listing_id, row_html in rows:
        listing = {"id": listing_id}
        
        # Fiyat
        price_match = re.search(r'searchResultsPriceValue[^>]*>([^<]+)<', row_html)
        if price_match:
            listing["price"] = price_match.group(1).strip()
        
        # Konum
        loc_match = re.search(r'searchResultsLocationValue[^>]*>(.*?)</td>', row_html, re.DOTALL)
        if loc_match:
            loc = re.sub(r'<[^>]+>', ' ', loc_match.group(1))
            listing["location"] = ' '.join(loc.split()).strip()
        
        # Tarih
        date_match = re.search(r'searchResultsDateValue[^>]*>(.*?)</td>', row_html, re.DOTALL)
        if date_match:
            date = re.sub(r'<[^>]+>', ' ', date_match.group(1))
            listing["date"] = ' '.join(date.split()).strip()
        
        # m2 ve oda sayısı
        attr_matches = re.findall(r'searchResultsAttributeValue[^>]*>([^<]+)<', row_html)
        if len(attr_matches) >= 1:
            listing["m2"] = attr_matches[0].strip()
        if len(attr_matches) >= 2:
            listing["room"] = attr_matches[1].strip()
        
        # URL
        url_match = re.search(r'href="(/ilan/[^"]+)"', row_html)
        if url_match:
            listing["url"] = url_match.group(1)
        
        listings.append(listing)
    
    return listings


class SahibindenScraper:
    """Hibrit Sahibinden Scraper"""
    
    BASE_URL = "https://www.sahibinden.com"
    
    def __init__(self):
        self.browser = None
        self.tab = None
        self.cookies = {}
        self.headers = {}
        self.curl_session = None
    
    async def start(self, headless: bool = False):
        """Browser başlat ve session hazırla."""
        print("🚀 Browser başlatılıyor...")
        self.browser = await uc.start(
            headless=headless,
            browser_args=["--no-sandbox", "--disable-gpu"],
        )
        self.tab = self.browser.main_tab
        
        # Ana sayfaya git
        print("🌐 Sahibinden.com'a bağlanılıyor...")
        await self.tab.get(self.BASE_URL)
        await self.tab.wait(3)
        
        # Çerez popup'ını kapat
        await handle_cookie_popup(self.tab)
        
        # Cookie'leri al
        await self._extract_session()
        
        print("✅ Scraper hazır!")
        return self
    
    async def _extract_session(self):
        """Browser'dan cookie ve header bilgilerini al."""
        try:
            # User agent al
            user_agent = await self.tab.evaluate("navigator.userAgent")
            self.headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                "Referer": self.BASE_URL,
            }
            
            # Cookie almayı atla - çok yavaş çalışıyor
            # Bunun yerine browser'dan direkt JS ile alalım
            try:
                cookies_str = await self.tab.evaluate("document.cookie")
                if cookies_str:
                    for cookie in cookies_str.split(";"):
                        if "=" in cookie:
                            name, value = cookie.strip().split("=", 1)
                            self.cookies[name] = value
                    print(f"🍪 {len(self.cookies)} cookie alındı")
            except:
                print("⚠️ Cookie alınamadı, devam ediliyor...")
            
            # curl_cffi session oluştur
            if CURL_CFFI_AVAILABLE and self.cookies:
                self.curl_session = AsyncSession(
                    impersonate="chrome120",
                    cookies=self.cookies,
                    headers=self.headers,
                    timeout=30,
                )
                print("⚡ curl_cffi aktif")
            
            print("✅ Scraper hazır!")
                
        except Exception as e:
            print(f"⚠️ Session hatası: {e}")
            print("✅ Scraper hazır (sadece browser modu)")
    
    async def scrape_page(self, url: str, use_curl: bool = True) -> list[dict]:
        """
        Tek bir sayfayı çek.
        use_curl=True ise önce curl_cffi dener.
        """
        # curl_cffi ile dene
        if use_curl and CURL_CFFI_AVAILABLE and self.curl_session:
            try:
                response = await self.curl_session.get(url)
                if response.status_code == 200:
                    listings = parse_html_listings(response.text)
                    if listings:
                        return listings
            except Exception as e:
                print(f"⚠️ curl_cffi hatası: {e}")
        
        # Browser ile çek
        return await scrape_with_js(self.tab, url)
    
    async def scrape_multiple_pages(
        self, 
        base_url: str, 
        max_pages: int = 5,
        delay: float = 1.0
    ) -> list[dict]:
        """
        Birden fazla sayfa çek.
        İlk sayfa browser ile, sonrakiler curl_cffi ile.
        """
        all_listings = []
        
        for page in range(max_pages):
            offset = page * 20  # Sahibinden 20 ilan/sayfa
            
            if "?" in base_url:
                url = f"{base_url}&pagingOffset={offset}"
            else:
                url = f"{base_url}?pagingOffset={offset}"
            
            print(f"\n📄 Sayfa {page + 1}/{max_pages}...")
            
            # İlk sayfa browser ile (güvenilir), sonrakiler curl ile (hızlı)
            use_curl = page > 0
            listings = await self.scrape_page(url, use_curl=use_curl)
            
            if not listings:
                print(f"⚠️ Sayfa {page + 1}'de ilan bulunamadı, durduruluyor.")
                break
            
            all_listings.extend(listings)
            print(f"   ✓ {len(listings)} ilan | Toplam: {len(all_listings)}")
            
            if page < max_pages - 1:
                await asyncio.sleep(delay)
        
        return all_listings
    
    async def close(self):
        """Kaynakları temizle."""
        if self.curl_session:
            await self.curl_session.close()
        if self.browser:
            self.browser.stop()
        print("👋 Scraper kapatıldı.")


async def handle_cookie_popup(tab):
    """Çerez kabul popup'ını kapat."""
    try:
        # JavaScript ile çerez butonunu bul ve tıkla
        js_code = """
        (() => {
            // Farklı çerez butonlarını dene
            const selectors = [
                'button[id*="accept"]',
                'button[class*="accept"]',
                'a[id*="accept"]',
                'button:contains("Kabul")',
                '#sp_message_iframe_953358',  // Sahibinden specific
            ];
            
            for (const sel of selectors) {
                try {
                    const btn = document.querySelector(sel);
                    if (btn) {
                        btn.click();
                        return true;
                    }
                } catch (e) {}
            }
            return false;
        })()
        """
        await tab.evaluate(js_code)
        await tab.wait(1)
    except:
        pass
    
    # nodriver find ile de dene
    try:
        for text in ["Kabul Et", "Tümünü Kabul Et", "Accept All"]:
            try:
                btn = await tab.find(text, best_match=True)
                if btn:
                    await btn.click()
                    print("🍪 Çerez popup'ı kapatıldı")
                    await tab.wait(1)
                    return
            except:
                continue
    except:
        pass


async def main():
    """
    Ana fonksiyon - Emlak scraping örneği
    """
    print("=" * 60)
    print("🏠 Sahibinden.com Emlak Scraper")
    print("   nodriver + curl_cffi hibrit sistem")
    print("=" * 60)
    
    scraper = SahibindenScraper()
    
    try:
        await scraper.start(headless=False)
        
        # ═══════════════════════════════════════════════════════════
        # ÖRNEK 1: Tek sayfa çek
        # ═══════════════════════════════════════════════════════════
        print("\n" + "─" * 50)
        print("📋 İstanbul Satılık Daire İlanları (1 sayfa)")
        print("─" * 50)
        
        url = "https://www.sahibinden.com/satilik-daire/istanbul"
        listings = await scraper.scrape_page(url, use_curl=False)
        
        print(f"\n✅ {len(listings)} ilan bulundu!")
        
        # İlk 5 ilanı göster
        for i, listing in enumerate(listings[:5], 1):
            title = listing.get('title', '') or f"İlan #{listing.get('id', 'N/A')}"
            print(f"\n  [{i}] {title[:60]}")
            print(f"      💰 {listing.get('price', 'N/A')}")
            print(f"      📍 {listing.get('location', 'N/A')}")
            print(f"      📐 {listing.get('m2', '?')} m² | {listing.get('room', '?')}")
        
        # ═══════════════════════════════════════════════════════════
        # ÖRNEK 2: Çoklu sayfa çek (curl_cffi hızlandırması ile)
        # ═══════════════════════════════════════════════════════════
        print("\n" + "─" * 50)
        print("📚 Çoklu Sayfa Çekme (3 sayfa)")
        print("─" * 50)
        
        all_listings = await scraper.scrape_multiple_pages(
            "https://www.sahibinden.com/satilik-daire/istanbul/kadikoy",
            max_pages=3,
            delay=1.5
        )
        
        print(f"\n✅ Toplam {len(all_listings)} ilan çekildi!")
        
        # Fiyat istatistikleri
        prices = []
        for l in all_listings:
            try:
                price_str = l.get('price', '').replace('.', '').replace(' TL', '').replace('TL', '').strip()
                if price_str.isdigit():
                    prices.append(int(price_str))
            except:
                pass
        
        if prices:
            print(f"\n📊 Fiyat İstatistikleri:")
            print(f"   Min: {min(prices):,} TL")
            print(f"   Max: {max(prices):,} TL")
            print(f"   Ort: {sum(prices)//len(prices):,} TL")
        
        # ═══════════════════════════════════════════════════════════
        # Sonuçları kaydet
        # ═══════════════════════════════════════════════════════════
        output_file = f"emlak_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "scrape_date": datetime.now().isoformat(),
                "total_listings": len(all_listings),
                "listings": all_listings,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Sonuçlar kaydedildi: {output_file}")
        
        # Bekle
        print("\n⏳ 5 saniye bekleniyor...")
        await scraper.tab.wait(5)
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await scraper.close()


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
