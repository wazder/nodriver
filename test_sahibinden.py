#!/usr/bin/env python
# coding: utf-8
"""
Sahibinden Scraper Test Script
Bu script sahibinden scraper'ın temel işlevlerini test eder.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nodriver as uc


async def test_sahibinden_access():
    """Sahibinden'e erişim testi"""
    print("=" * 60)
    print("TEST: Sahibinden.com Erişim Testi")
    print("=" * 60)
    
    browser = await uc.start(headless=True)
    tab = browser.main_tab
    
    try:
        print("\n🌐 Sahibinden.com'a gidiliyor...")
        await tab.get('https://www.sahibinden.com')
        await tab.sleep(3)
        
        # Sayfa yüklendi mi?
        current_url = tab.url
        print(f"   URL: {current_url}")
        
        # Cloudflare/bot koruması var mı kontrol et
        content = await tab.get_content()
        
        if "Just a moment" in content or "challenge" in content.lower():
            print("   ⚠️ Cloudflare challenge tespit edildi!")
            print("   Bekleniyor...")
            await tab.sleep(5)
            content = await tab.get_content()
        
        # Ana sayfa yüklendi mi kontrol et
        if "sahibinden" in content.lower():
            print("   ✅ Sahibinden ana sayfası yüklendi!")
            return True, browser, tab
        else:
            print("   ❌ Sayfa düzgün yüklenmedi")
            return False, browser, tab
            
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return False, browser, tab


async def test_listing_page(browser, tab):
    """İlan listesi sayfası testi"""
    print("\n" + "=" * 60)
    print("TEST: İlan Listesi Sayfası")
    print("=" * 60)
    
    try:
        # Satılık daire sayfasına git
        url = "https://www.sahibinden.com/satilik-daire/istanbul"
        print(f"\n🌐 Gidiliyor: {url}")
        await tab.get(url)
        await tab.sleep(3)
        
        print(f"   URL: {tab.url}")
        
        # İlan kartlarını bul
        cards = await tab.select_all("tr.searchResultsItem", timeout=5)
        
        if not cards:
            print("   ⚠️ tr.searchResultsItem bulunamadı, alternatif deneniyor...")
            cards = await tab.select_all("tbody tr[data-id]", timeout=5)
        
        if not cards:
            print("   ⚠️ Alternatif de bulunamadı, tüm tr'leri deniyorum...")
            cards = await tab.select_all("table tbody tr", timeout=5)
        
        print(f"   📋 {len(cards)} ilan satırı bulundu")
        
        if len(cards) > 0:
            print("\n   İlk 3 ilanın bilgileri:")
            for i, card in enumerate(cards[:3]):
                try:
                    # Data-id attribute
                    data_id = None
                    try:
                        data_id = card.attrs.get('data-id', 'N/A')
                    except:
                        pass
                    
                    print(f"\n   [{i+1}] İlan ID: {data_id}")
                    print(f"       HTML: {str(card)[:100]}...")
                except Exception as e:
                    print(f"   [{i+1}] Parse hatası: {e}")
            
            return True
        else:
            print("   ❌ Hiç ilan bulunamadı")
            
            # Sayfa içeriğini kontrol et
            content = await tab.get_content()
            if "robot" in content.lower() or "captcha" in content.lower():
                print("   ⚠️ Bot koruması aktif olabilir!")
            
            return False
            
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_element_selectors(browser, tab):
    """Element selector testi"""
    print("\n" + "=" * 60)
    print("TEST: Element Selectors")
    print("=" * 60)
    
    try:
        # Farklı selector'ları dene
        selectors_to_test = [
            ("Logo", "a.logo-link, .logo, a[href='/']"),
            ("Arama kutusu", "input[type='text'], input.search-input, #searchText"),
            ("Kategori menüsü", ".category-list, .categories, nav"),
            ("Footer", "footer, .footer, #footer"),
        ]
        
        for name, selector in selectors_to_test:
            try:
                elem = await tab.select(selector, timeout=2)
                if elem:
                    print(f"   ✅ {name} bulundu: {str(elem)[:50]}...")
                else:
                    print(f"   ⚠️ {name} bulunamadı ({selector})")
            except Exception as e:
                print(f"   ⚠️ {name} hatası: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return False


async def test_javascript_eval(browser, tab):
    """JavaScript çalıştırma testi"""
    print("\n" + "=" * 60)
    print("TEST: JavaScript Evaluation")
    print("=" * 60)
    
    try:
        # Sayfa başlığını al
        title = await tab.evaluate("document.title")
        print(f"   ✅ Sayfa başlığı: {title}")
        
        # İlan sayısını bulmaya çalış
        try:
            count_text = await tab.evaluate("""
                (() => {
                    const el = document.querySelector('.result-text, .searchResultsCount, .totalCount');
                    return el ? el.innerText : 'Bulunamadı';
                })()
            """)
            print(f"   ✅ İlan sayısı elementi: {count_text}")
        except:
            print("   ⚠️ İlan sayısı bulunamadı")
        
        # Tüm ilan ID'lerini al
        try:
            ids = await tab.evaluate("""
                (() => {
                    const rows = document.querySelectorAll('tr[data-id]');
                    return Array.from(rows).slice(0, 5).map(r => r.getAttribute('data-id'));
                })()
            """)
            print(f"   ✅ İlk 5 ilan ID: {ids}")
        except Exception as e:
            print(f"   ⚠️ İlan ID'leri alınamadı: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return False


async def main():
    """Ana test fonksiyonu"""
    print("\n" + "=" * 70)
    print("SAHİBİNDEN SCRAPER TEST SÜİTİ")
    print("=" * 70)
    
    results = []
    
    # Test 1: Erişim testi
    success, browser, tab = await test_sahibinden_access()
    results.append(("Sahibinden Erişim", success))
    
    if success:
        # Test 2: İlan listesi
        result = await test_listing_page(browser, tab)
        results.append(("İlan Listesi", result))
        
        # Test 3: Element selectors
        result = await test_element_selectors(browser, tab)
        results.append(("Element Selectors", result))
        
        # Test 4: JavaScript
        result = await test_javascript_eval(browser, tab)
        results.append(("JavaScript Eval", result))
    
    # Temizlik
    try:
        browser.stop()
    except:
        pass
    
    # Sonuçları göster
    print("\n" + "=" * 70)
    print("TEST SONUÇLARI")
    print("=" * 70)
    
    passed = 0
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {name}: {status}")
        if result:
            passed += 1
    
    print("-" * 70)
    print(f"   Toplam: {passed}/{len(results)} test başarılı")
    print("=" * 70)
    
    return passed == len(results)


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
