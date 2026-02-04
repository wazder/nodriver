#!/usr/bin/env python
# coding: utf-8
"""
Sahibinden Scraper - İlk Çıktı
Gerçek ilan verilerini çeker ve gösterir.
"""

import asyncio
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nodriver as uc


async def scrape_listings():
    """Sahibinden'den ilan çek"""
    print("=" * 70)
    print("SAHİBİNDEN.COM - İLAN ÇEKME")
    print("=" * 70)
    
    browser = await uc.start(headless=False)
    tab = browser.main_tab
    
    results = []
    
    try:
        # Önce ana sayfaya git
        print("\n🌐 Önce ana sayfaya gidiliyor...")
        await tab.get('https://www.sahibinden.com')
        await tab.sleep(3)
        
        # Cloudflare kontrolü
        content = await tab.get_content()
        if "challenge" in content.lower() or "olağan dışı" in content.lower():
            print("⏳ Cloudflare challenge - 15 saniye bekleniyor...")
            await tab.sleep(15)
        
        # İlan listesine git
        print("\n🌐 İstanbul satılık daire sayfasına gidiliyor...")
        await tab.get('https://www.sahibinden.com/satilik-daire/istanbul')
        await tab.sleep(5)
        
        print(f"📍 URL: {tab.url}")
        
        # JavaScript ile ilanları çek
        print("\n📋 İlanlar çekiliyor...")
        
        listings = await tab.evaluate("""
            (() => {
                const rows = document.querySelectorAll('tr.searchResultsItem');
                const results = [];
                
                rows.forEach((row, index) => {
                    try {
                        const listing = {};
                        
                        // İlan ID
                        listing.id = row.getAttribute('data-id') || '';
                        
                        // Başlık ve URL
                        const titleLink = row.querySelector('td.searchResultsTitleValue a');
                        if (titleLink) {
                            listing.title = titleLink.innerText.trim();
                            listing.url = titleLink.href;
                        }
                        
                        // Fiyat
                        const priceEl = row.querySelector('td.searchResultsPriceValue');
                        if (priceEl) {
                            listing.price = priceEl.innerText.trim().replace(/\\s+/g, ' ');
                        }
                        
                        // Konum
                        const locEl = row.querySelector('td.searchResultsLocationValue');
                        if (locEl) {
                            listing.location = locEl.innerText.trim().replace(/\\s+/g, ' ');
                        }
                        
                        // Tarih
                        const dateEl = row.querySelector('td.searchResultsDateValue');
                        if (dateEl) {
                            listing.date = dateEl.innerText.trim().replace(/\\s+/g, ' ');
                        }
                        
                        // Özellikler (m2, oda sayısı vs.)
                        const attrEls = row.querySelectorAll('td.searchResultsAttributeValue');
                        listing.attributes = [];
                        attrEls.forEach(el => {
                            const text = el.innerText.trim();
                            if (text) listing.attributes.push(text);
                        });
                        
                        if (listing.id && listing.title) {
                            results.push(listing);
                        }
                    } catch (e) {}
                });
                
                return results;
            })()
        """)
        
        print(f"\n✅ {len(listings)} ilan bulundu!\n")
        print("=" * 70)
        
        # İlanları göster
        for i, listing in enumerate(listings[:10], 1):
            print(f"\n[{i}] {listing.get('title', 'N/A')[:60]}")
            print(f"    💰 Fiyat: {listing.get('price', 'N/A')}")
            print(f"    📍 Konum: {listing.get('location', 'N/A')}")
            print(f"    📅 Tarih: {listing.get('date', 'N/A')}")
            if listing.get('attributes'):
                print(f"    📐 Özellikler: {' | '.join(listing['attributes'])}")
            print(f"    🔗 ID: {listing.get('id', 'N/A')}")
        
        # JSON olarak kaydet
        output = {
            "scrape_date": datetime.now().isoformat(),
            "source": "sahibinden.com",
            "category": "satilik-daire",
            "city": "istanbul",
            "total_count": len(listings),
            "listings": listings
        }
        
        filename = f"sahibinden_output_{datetime.now().strftime('%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'=' * 70}")
        print(f"💾 Sonuçlar kaydedildi: {filename}")
        print(f"📊 Toplam: {len(listings)} ilan")
        print("=" * 70)
        
        results = listings
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await tab.sleep(2)
        browser.stop()
    
    return results


if __name__ == "__main__":
    asyncio.run(scrape_listings())
