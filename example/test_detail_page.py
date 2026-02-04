"""
Sahibinden detay sayfası yapısını test et
"""
import asyncio
import nodriver as uc

async def main():
    browser = await uc.start()
    
    # Önce ana siteye git
    print("Ana siteye gidiliyor...")
    page = await browser.get("https://www.sahibinden.com")
    await asyncio.sleep(3)
    
    # Çerez popup'ını kapat
    try:
        accept_btn = await page.find("Kabul Et", timeout=3)
        if accept_btn:
            await accept_btn.click()
            await asyncio.sleep(1)
    except:
        pass
    
    # Test ilanı
    test_url = "https://sahibinden.com/ilan/emlak-is-yeri-kiralik-atasehir-finans-merkezi-sarphan-in-en-gozde-yeri-1281717159/detay"
    print(f"\nDetay sayfasına gidiliyor: {test_url}")
    await page.get(test_url)
    await asyncio.sleep(3)
    
    # Sayfa yapısını incele
    debug_js = """
    (() => {
        const result = {};
        
        // URL ve title
        result.url = window.location.href;
        result.title = document.title;
        
        // Fiyat alanları
        result.priceDiv = document.querySelector('.classifiedInfo h3')?.innerText || 'none';
        result.priceSpan = document.querySelector('span[class*="price"]')?.innerText || 'none';
        result.priceH3 = document.querySelector('h3')?.innerText || 'none';
        
        // Başlık
        result.titleH1 = document.querySelector('h1')?.innerText || 'none';
        result.classifiedTitle = document.querySelector('.classifiedDetailTitle h1')?.innerText || 'none';
        
        // ID
        result.classifiedId = document.querySelector('.classifiedId span')?.innerText || 'none';
        result.classifiedIdAlt = document.body.innerHTML.match(/İlan No[^<]*<[^>]*>([0-9]+)/)?.[1] || 'none';
        
        // Açıklama
        result.descriptionDiv = document.querySelector('#classifiedDescription')?.innerText?.substring(0, 200) || 'none';
        result.description2 = document.querySelector('[class*="description"]')?.innerText?.substring(0, 200) || 'none';
        
        // Fotoğraflar - çeşitli yollar
        result.galleryImages = document.querySelectorAll('.classifiedDetailPhotos img').length;
        result.thumbImages = document.querySelectorAll('.thumbs img').length;
        result.allImages = document.querySelectorAll('img[src*="shbdn"]').length;
        result.carouselImages = document.querySelectorAll('[class*="carousel"] img, [class*="gallery"] img, [class*="photo"] img').length;
        
        // İlk 3 resim URL'si
        const imgList = [];
        document.querySelectorAll('img').forEach((img, i) => {
            if (i < 10 && img.src && (img.src.includes('shbdn') || img.src.includes('sahibinden'))) {
                imgList.push(img.src);
            }
        });
        result.sampleImages = imgList;
        
        // Özellik tablosu
        result.infoTable = document.querySelectorAll('.classifiedInfoList li').length;
        result.infoTable2 = document.querySelectorAll('ul.classifiedInfoList li').length;
        result.allLists = document.querySelectorAll('ul li').length;
        
        // Satıcı bilgisi
        result.sellerName = document.querySelector('.username-info-area')?.innerText || 'none';
        result.sellerStore = document.querySelector('.store-name')?.innerText || 'none';
        result.sellerPhone = document.querySelector('[class*="phone"]')?.innerText || 'none';
        
        // Konum
        result.location = document.querySelector('.classifiedInfo h2')?.innerText || 'none';
        result.breadcrumb = document.querySelector('.breadcrumb')?.innerText || 'none';
        
        // Detaylı özellikler
        const specs = {};
        document.querySelectorAll('.classifiedInfoList li').forEach(li => {
            const label = li.querySelector('strong')?.innerText || '';
            const value = li.querySelector('span')?.innerText || '';
            if (label && value) specs[label.trim()] = value.trim();
        });
        result.specifications = specs;
        
        // HTML boyutu
        result.htmlLength = document.body.innerHTML.length;
        
        // Tüm class'ları listele (önemli olanlar)
        const classes = new Set();
        document.querySelectorAll('[class]').forEach(el => {
            el.className.split(' ').forEach(c => {
                if (c.includes('classified') || c.includes('photo') || c.includes('price') || c.includes('info')) {
                    classes.add(c);
                }
            });
        });
        result.relevantClasses = Array.from(classes).slice(0, 30);
        
        return result;
    })()
    """
    
    print("\n=== SAYFA YAPISI ANALİZİ ===\n")
    result = await page.evaluate(debug_js)
    
    # Sonuçları yazdır
    for key, value in result.items():
        if isinstance(value, dict):
            print(f"\n{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        elif isinstance(value, list):
            print(f"\n{key}:")
            for item in value[:5]:
                print(f"  - {item}")
            if len(value) > 5:
                print(f"  ... ve {len(value) - 5} tane daha")
        else:
            print(f"{key}: {value}")
    
    # Biraz bekle
    input("\n\nEnter'a basarak tarayıcıyı kapatın...")
    
if __name__ == "__main__":
    uc.loop().run_until_complete(main())
