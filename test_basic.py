#!/usr/bin/env python
# coding: utf-8
"""
Nodriver temel test scripti
Bu script, nodriver kütüphanesinin temel fonksiyonlarını test eder.
"""

import asyncio
import sys

try:
    import nodriver as uc
except ImportError:
    print("❌ nodriver import edilemedi!")
    sys.exit(1)


async def test_basic():
    """Temel browser başlatma ve sayfa yükleme testi"""
    print("=" * 60)
    print("NODRIVER TEMEL TEST")
    print("=" * 60)
    
    print("\n🚀 1. Browser başlatılıyor...")
    try:
        browser = await uc.start(headless=True)
        print("   ✅ Browser başarıyla başlatıldı!")
        print(f"   - WebSocket URL: {browser.websocket_url}")
        print(f"   - Tab sayısı: {len(browser.tabs)}")
    except Exception as e:
        print(f"   ❌ Browser başlatma hatası: {e}")
        import traceback
        traceback.print_exc()
        return False

    try:
        tab = browser.main_tab
        print(f"   - Main tab: {tab}")
        
        print("\n🌐 2. Sayfa yükleniyor (example.com)...")
        await tab.get('https://example.com')
        await tab.sleep(2)
        
        print(f"   ✅ Sayfa yüklendi!")
        print(f"   - URL: {tab.url}")
        print(f"   - Title: {tab.title}")
        
        print("\n🔍 3. Element seçme testi...")
        h1 = await tab.select('h1', timeout=5)
        if h1:
            print(f"   ✅ H1 elementi bulundu: {h1}")
            html = await h1.get_html()
            print(f"   - HTML içeriği: {html[:100]}")
        else:
            print("   ⚠️ H1 elementi bulunamadı")
        
        print("\n🔎 4. Text ile arama testi...")
        element = await tab.find("Example Domain", timeout=5)
        if element:
            print(f"   ✅ Element bulundu: {element}")
        else:
            print("   ⚠️ Element bulunamadı")
        
        print("\n🛑 5. Browser kapatılıyor...")
        browser.stop()
        print("   ✅ Browser kapatıldı!")
        
        print("\n" + "=" * 60)
        print("TEST SONUCU: BAŞARILI ✅")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Test sırasında hata: {e}")
        import traceback
        traceback.print_exc()
        try:
            browser.stop()
        except:
            pass
        return False


if __name__ == "__main__":
    result = asyncio.run(test_basic())
    sys.exit(0 if result else 1)
