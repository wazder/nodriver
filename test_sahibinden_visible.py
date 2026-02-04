#!/usr/bin/env python
# coding: utf-8
"""
Sahibinden Scraper - Detaylı Analiz
Headless=False ile çalışarak gerçek durumu görür.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nodriver as uc


async def analyze_sahibinden():
    """Sahibinden'i detaylı analiz et"""
    print("=" * 70)
    print("SAHİBİNDEN.COM DETAYLI ANALİZ")
    print("(Browser görünür modda açılacak)")
    print("=" * 70)
    
    # Headless=False ile başlat
    browser = await uc.start(headless=False)
    tab = browser.main_tab
    
    try:
        # 1. Ana sayfa
        print("\n[1/4] Ana sayfaya gidiliyor...")
        await tab.get('https://www.sahibinden.com')
        await tab.sleep(5)
        
        print(f"   URL: {tab.url}")
        title = await tab.evaluate("document.title")
        print(f"   Title: {title}")
        
        # Cloudflare kontrolü
        content = await tab.get_content()
        if "challenge" in content.lower() or "just a moment" in content.lower():
            print("   ⚠️ Cloudflare challenge - 10 saniye bekleniyor...")
            await tab.sleep(10)
        
        # 2. İlan listesi sayfası
        print("\n[2/4] İlan listesi sayfasına gidiliyor...")
        await tab.get('https://www.sahibinden.com/satilik-daire/istanbul')
        await tab.sleep(5)
        
        print(f"   URL: {tab.url}")
        
        # Sayfa kaynağını kontrol et
        content = await tab.get_content()
        content_len = len(content)
        print(f"   Sayfa boyutu: {content_len} karakter")
        
        # HTML yapısını analiz et
        print("\n[3/4] Sayfa yapısı analiz ediliyor...")
        
        # Farklı selector'ları dene
        selectors = [
            ("tr.searchResultsItem", "İlan satırları"),
            ("tbody tr[data-id]", "Data-id'li satırlar"),
            (".searchResultsRowClass", "searchResultsRowClass"),
            (".classified-list", "classified-list"),
            ("article", "Article elementleri"),
            ("[data-id]", "Herhangi bir data-id"),
        ]
        
        for selector, desc in selectors:
            try:
                elements = await tab.select_all(selector, timeout=2)
                print(f"   {desc} ({selector}): {len(elements)} adet")
            except:
                print(f"   {desc} ({selector}): Timeout/Hata")
        
        # JavaScript ile kontrol
        print("\n[4/4] JavaScript ile kontrol...")
        
        # Tüm class'ları listele
        classes = await tab.evaluate("""
            (() => {
                const all = document.querySelectorAll('*');
                const classes = new Set();
                all.forEach(el => {
                    el.classList.forEach(c => {
                        if (c.toLowerCase().includes('search') || 
                            c.toLowerCase().includes('result') ||
                            c.toLowerCase().includes('listing') ||
                            c.toLowerCase().includes('classified')) {
                            classes.add(c);
                        }
                    });
                });
                return Array.from(classes).slice(0, 20);
            })()
        """)
        print(f"   İlgili class'lar: {classes}")
        
        # Table var mı?
        tables = await tab.evaluate("document.querySelectorAll('table').length")
        print(f"   Table sayısı: {tables}")
        
        # tbody içindeki tr'ler
        trs = await tab.evaluate("document.querySelectorAll('tbody tr').length")
        print(f"   tbody tr sayısı: {trs}")
        
        # İlan ID'leri
        ids = await tab.evaluate("""
            (() => {
                const rows = document.querySelectorAll('[data-id]');
                return Array.from(rows).slice(0, 10).map(r => ({
                    tag: r.tagName,
                    id: r.getAttribute('data-id'),
                    class: r.className.slice(0, 50)
                }));
            })()
        """)
        print(f"   data-id elementleri: {ids}")
        
        # Sonuç
        print("\n" + "=" * 70)
        print("ANALİZ SONUCU")
        print("=" * 70)
        
        if content_len < 5000:
            print("❌ SORUN: Sayfa içeriği çok kısa - muhtemelen Cloudflare blokladı")
            print("   Çözüm: Headless=False ile manuel kullanım veya beklemeli scraping")
        elif trs == 0 and not ids:
            print("⚠️ SORUN: Sayfa yüklendi ama ilan bulunamadı")
            print("   Cloudflare challenge geçilmiş olabilir ama içerik dinamik yükleniyor olabilir")
        else:
            print("✅ Sayfa yüklendi ve ilanlar mevcut!")
        
        # 10 saniye bekle ve kullanıcıya göster
        print("\n⏳ 10 saniye beklenip browser kapatılacak...")
        print("   (Bu sürede sayfayı inceleyebilirsiniz)")
        await tab.sleep(10)
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        browser.stop()
        print("\n✅ Browser kapatıldı")


if __name__ == "__main__":
    asyncio.run(analyze_sahibinden())
