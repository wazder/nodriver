# coding: utf-8
"""
Cihangir Emlak Scraper - 1000 ilan
"""

import asyncio
import json
from datetime import datetime

try:
    import nodriver as uc
except (ModuleNotFoundError, ImportError):
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import nodriver as uc


async def handle_cookie_popup(tab):
    """Çerez popup'ını kapat."""
    try:
        for text in ["Kabul Et", "Tümünü Kabul Et", "Kabul"]:
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


async def scrape_page(tab, url: str) -> list[dict]:
    """Tek sayfa scrape et."""
    print(f"🌐 Sayfa yükleniyor: {url[:80]}...")
    await tab.get(url)
    await tab.wait(3)
    
    js_code = """
    (() => {
        const listings = [];
        const rows = document.querySelectorAll('tr.searchResultsItem');
        
        rows.forEach((row, index) => {
            try {
                const listing = {};
                
                listing.id = row.getAttribute('data-id') || '';
                
                let titleLink = row.querySelector('a.classifiedTitle');
                if (!titleLink) {
                    const titleCell = row.querySelector('td.searchResultsTitleValue');
                    if (titleCell) {
                        titleLink = titleCell.querySelector('a[href*="/ilan/"]');
                    }
                }
                if (!titleLink) {
                    titleLink = row.querySelector('a[href*="/ilan/"]');
                }
                
                if (titleLink) {
                    const href = titleLink.getAttribute('href') || '';
                    listing.url = href.startsWith('/') ? 'https://www.sahibinden.com' + href : href;
                    listing.title = titleLink.getAttribute('title') || 
                                   titleLink.innerText.replace(/\\s+/g, ' ').trim() || '';
                } else {
                    listing.url = '';
                    listing.title = '';
                }
                
                const priceEl = row.querySelector('td.searchResultsPriceValue');
                if (priceEl) listing.price = priceEl.innerText.trim();
                
                const locEl = row.querySelector('td.searchResultsLocationValue');
                if (locEl) listing.location = locEl.innerText.replace(/\\n/g, ' ').trim();
                
                const dateEl = row.querySelector('td.searchResultsDateValue');
                if (dateEl) listing.date = dateEl.innerText.replace(/\\n/g, ' ').trim();
                
                const attrEls = row.querySelectorAll('td.searchResultsAttributeValue');
                listing.m2 = attrEls[0] ? attrEls[0].innerText.trim() : '';
                listing.room = attrEls[1] ? attrEls[1].innerText.trim() : '';
                
                const imgEl = row.querySelector('img');
                if (imgEl) {
                    listing.image = imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '';
                }
                
                if (listing.id) listings.push(listing);
            } catch (e) {}
        });
        
        return listings;
    })()
    """
    
    try:
        result = await tab.evaluate(js_code)
        listings = []
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    if "value" in item and isinstance(item["value"], list):
                        flat = {}
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
        return listings
    except Exception as e:
        print(f"⚠️ Hata: {e}")
        return []


async def main():
    print("=" * 60)
    print("🏠 İstanbul Cihangir - 1000 Ev Scraper")
    print("=" * 60)
    
    browser = await uc.start(headless=False, lang="tr-TR")
    tab = browser.main_tab
    
    try:
        # Ana sayfaya git
        print("🌐 Sahibinden.com'a bağlanılıyor...")
        await tab.get("https://www.sahibinden.com")
        await tab.wait(3)
        await handle_cookie_popup(tab)
        
        all_listings = []
        base_url = "https://www.sahibinden.com/satilik-daire/istanbul-beyoglu-cihangir"
        
        # 1000 ilan için ~50 sayfa (her sayfa ~20 ilan)
        max_pages = 60  # Biraz fazla çekelim, Cihangir'de o kadar ilan olmayabilir
        target_count = 1000
        
        for page in range(max_pages):
            if len(all_listings) >= target_count:
                print(f"\n🎯 Hedef {target_count} ilana ulaşıldı!")
                break
            
            if page == 0:
                url = base_url
            else:
                offset = page * 20
                url = f"{base_url}?pagingOffset={offset}"
            
            print(f"\n📄 Sayfa {page + 1}/{max_pages}...")
            listings = await scrape_page(tab, url)
            
            if not listings:
                print("⚠️ Sayfa boş veya son sayfaya ulaşıldı.")
                break
            
            # Duplicate kontrolü
            existing_ids = {l.get('id') for l in all_listings}
            new_listings = [l for l in listings if l.get('id') not in existing_ids]
            
            if not new_listings:
                print("⚠️ Yeni ilan yok, muhtemelen son sayfa.")
                break
            
            all_listings.extend(new_listings)
            print(f"   ✓ {len(new_listings)} yeni ilan | Toplam: {len(all_listings)}")
            
            # Rate limiting
            await tab.wait(2)
        
        print(f"\n{'=' * 60}")
        print(f"✅ Toplam {len(all_listings)} ilan çekildi!")
        
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
        
        # Kaydet
        output_file = f"cihangir_evler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "scrape_date": datetime.now().isoformat(),
                "location": "İstanbul Beyoğlu Cihangir",
                "total_listings": len(all_listings),
                "listings": all_listings,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Sonuçlar kaydedildi: {output_file}")
        
        print("\n⏳ 3 saniye bekleniyor...")
        await tab.wait(3)
        
    finally:
        browser.stop()
        print("👋 Browser kapatıldı")


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
