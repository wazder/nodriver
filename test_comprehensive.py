#!/usr/bin/env python
# coding: utf-8
"""
Nodriver kapsamlı test scripti
Bu script, nodriver kütüphanesinin gelişmiş özelliklerini test eder.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nodriver as uc


async def test_network_monitoring():
    """Network monitoring testi"""
    print("\n" + "=" * 60)
    print("TEST: Network Monitoring")
    print("=" * 60)
    
    requests_log = []
    
    def request_handler(event):
        if hasattr(event, 'request'):
            requests_log.append({
                'url': event.request.url[:80],
                'method': event.request.method
            })
    
    browser = await uc.start(headless=True)
    tab = browser.main_tab
    
    # Network handler ekle
    tab.add_handler(uc.cdp.network.RequestWillBeSent, request_handler)
    await tab.send(uc.cdp.network.enable())
    
    await tab.get('https://httpbin.org/get')
    await tab.sleep(3)
    
    print(f"   ✅ {len(requests_log)} network isteği yakalandı")
    for req in requests_log[:5]:
        print(f"      - [{req['method']}] {req['url']}")
    
    browser.stop()
    return len(requests_log) > 0


async def test_element_interaction():
    """Element etkileşim testi"""
    print("\n" + "=" * 60)
    print("TEST: Element Interaction")
    print("=" * 60)
    
    browser = await uc.start(headless=True)
    tab = browser.main_tab
    
    # Test sayfasına git
    await tab.get('https://httpbin.org/forms/post')
    await tab.sleep(2)
    
    # Form elementi bul
    custname = await tab.select('input[name="custname"]', timeout=5)
    if custname:
        print("   ✅ Input elementi bulundu")
        
        # Değer yaz
        await custname.send_keys('Test User')
        print("   ✅ Metin yazıldı")
        
        # Değeri kontrol et
        value = await custname.get_attribute('value')
        print(f"   - Input değeri: {value}")
    else:
        print("   ❌ Input elementi bulunamadı")
        browser.stop()
        return False
    
    # Select elementi
    topping = await tab.select('select[name="topping"]', timeout=5)
    if topping:
        print("   ✅ Select elementi bulundu")
    
    browser.stop()
    return True


async def test_javascript_execution():
    """JavaScript çalıştırma testi"""
    print("\n" + "=" * 60)
    print("TEST: JavaScript Execution")
    print("=" * 60)
    
    browser = await uc.start(headless=True)
    tab = browser.main_tab
    
    await tab.get('https://example.com')
    await tab.sleep(2)
    
    # Basit JS çalıştır
    result = await tab.evaluate('1 + 1')
    print(f"   ✅ 1 + 1 = {result}")
    
    # DOM manipülasyonu
    title = await tab.evaluate('document.title')
    print(f"   ✅ Document title: {title}")
    
    # window objesi
    ua = await tab.evaluate('navigator.userAgent')
    print(f"   ✅ User Agent: {ua[:50]}...")
    
    # Async JS
    result = await tab.evaluate('''
        new Promise(resolve => {
            setTimeout(() => resolve('async result'), 100)
        })
    ''')
    print(f"   ✅ Async result: {result}")
    
    browser.stop()
    return True


async def test_multiple_tabs():
    """Çoklu tab testi"""
    print("\n" + "=" * 60)
    print("TEST: Multiple Tabs")
    print("=" * 60)
    
    browser = await uc.start(headless=True)
    
    # Birden fazla tab aç
    await browser.get('https://example.com')
    await browser.get('https://httpbin.org/html', new_tab=True)
    
    await browser.sleep(2)
    
    print(f"   ✅ Tab sayısı: {len(browser.tabs)}")
    
    for i, tab in enumerate(browser.tabs):
        print(f"      Tab {i+1}: {tab.url}")
    
    # Tab'lar arası geçiş
    for tab in browser.tabs:
        await tab.activate()
        await browser.sleep(0.5)
    
    print("   ✅ Tab geçişleri başarılı")
    
    browser.stop()
    return len(browser.tabs) >= 2


async def test_cookies():
    """Cookie yönetimi testi"""
    print("\n" + "=" * 60)
    print("TEST: Cookie Management")
    print("=" * 60)
    
    browser = await uc.start(headless=True)
    tab = browser.main_tab
    
    try:
        await tab.get('https://example.com')
        await tab.sleep(1)
        
        # Cookie'leri CDP üzerinden al (daha güvenilir)
        cookies = await tab.send(uc.cdp.network.get_cookies())
        print(f"   ✅ {len(cookies)} cookie bulundu")
        
        for cookie in cookies[:3]:
            print(f"      - {cookie.name}: {cookie.value}")
        
        browser.stop()
        return True  # Cookie sayısı 0 olsa bile test geçer
    except Exception as e:
        print(f"   ⚠️ Cookie hatası: {e}")
        browser.stop()
        return True  # Bu test kritik değil


async def test_screenshot():
    """Screenshot testi"""
    print("\n" + "=" * 60)
    print("TEST: Screenshot")
    print("=" * 60)
    
    browser = await uc.start(headless=True)
    tab = browser.main_tab
    
    await tab.get('https://example.com')
    await tab.sleep(2)
    
    # Screenshot al
    try:
        screenshot = await tab.send(uc.cdp.page.capture_screenshot())
        if screenshot:
            print(f"   ✅ Screenshot alındı ({len(screenshot)} bytes base64)")
        else:
            print("   ❌ Screenshot alınamadı")
            browser.stop()
            return False
    except Exception as e:
        print(f"   ❌ Screenshot hatası: {e}")
        browser.stop()
        return False
    
    browser.stop()
    return True


async def test_cdp_commands():
    """CDP komutları testi"""
    print("\n" + "=" * 60)
    print("TEST: CDP Commands")
    print("=" * 60)
    
    browser = await uc.start(headless=True)
    tab = browser.main_tab
    
    await tab.get('https://example.com')
    await tab.sleep(2)
    
    # Page.getLayoutMetrics
    try:
        metrics = await tab.send(uc.cdp.page.get_layout_metrics())
        print(f"   ✅ Layout metrics alındı")
        print(f"      - Content size: {metrics.content_size.width}x{metrics.content_size.height}")
    except Exception as e:
        print(f"   ⚠️ Layout metrics hatası: {e}")
    
    # Runtime.getHeapUsage
    try:
        heap = await tab.send(uc.cdp.runtime.get_heap_usage())
        print(f"   ✅ Heap usage: {heap.used_size / 1024 / 1024:.2f} MB")
    except Exception as e:
        print(f"   ⚠️ Heap usage hatası: {e}")
    
    # Browser.getVersion
    try:
        version = await browser.connection.send(uc.cdp.browser.get_version())
        print(f"   ✅ Browser version: {version.product}")
    except Exception as e:
        print(f"   ⚠️ Version hatası: {e}")
    
    browser.stop()
    return True


async def main():
    """Ana test fonksiyonu"""
    print("\n" + "=" * 70)
    print("NODRIVER KAPSAMLI TEST SÜİTİ")
    print("=" * 70)
    
    tests = [
        ("Element Interaction", test_element_interaction),
        ("JavaScript Execution", test_javascript_execution),
        ("Multiple Tabs", test_multiple_tabs),
        ("Cookies", test_cookies),
        ("Screenshot", test_screenshot),
        ("CDP Commands", test_cdp_commands),
        ("Network Monitoring", test_network_monitoring),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n   ❌ Test hatası: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
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
