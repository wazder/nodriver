"""
Sahibinden.com Scraper v3 - Multi Account Edition
=================================================
- Otomatik hesap rotasyonu
- Rate limit algılama ve hesap değiştirme
- Kendi domain'inden hesap yönetimi

Kullanım:
1. İlk önce hesaplar oluştur: python account_manager.py --create 3
2. Sonra scraper'ı çalıştır: python sahibinden_v3.py
"""

import asyncio
import json
import random
import re
import imaplib
import email
from datetime import datetime, timedelta
from pathlib import Path
import time

import nodriver as uc

# Account Manager'ı import et
from account_manager import AccountManager, DomainEmailHandler, DOMAIN_CONFIG

# Dosyalar
COOKIE_FILE = Path(__file__).parent / "sahibinden_cookies.json"
DATA_DIR = Path(__file__).parent / "kellerwilliams_data"
DATA_DIR.mkdir(exist_ok=True)

# Global manager
manager = AccountManager()
email_handler = DomainEmailHandler()


def get_2fa_from_domain(target_email: str, max_wait: int = 90) -> str | None:
    """Domain email'den 2FA kodunu oku"""
    return email_handler.get_verification_code(target_email, max_wait)


async def type_like_human(page, text):
    """İnsan gibi tek tek karakter yaz"""
    for char in text:
        if char == '@':
            await page.send(uc.cdp.input_.dispatch_key_event(
                type_="char",
                text="@"
            ))
        elif char == '.':
            await page.send(uc.cdp.input_.dispatch_key_event(
                type_="char",
                text="."
            ))
        elif char.isupper() or char in '!@#$%^&*()_+{}|:"<>?':
            await page.send(uc.cdp.input_.dispatch_key_event(
                type_="char",
                text=char
            ))
        else:
            await page.send(uc.cdp.input_.dispatch_key_event(
                type_="keyDown",
                text=char,
                key=char
            ))
            await page.send(uc.cdp.input_.dispatch_key_event(
                type_="keyUp",
                key=char
            ))
        
        await asyncio.sleep(random.uniform(0.05, 0.12))


async def press_key(page, key, code, keycode):
    """Tek tuş bas"""
    await page.send(uc.cdp.input_.dispatch_key_event(
        type_="keyDown",
        key=key,
        code=code,
        windows_virtual_key_code=keycode
    ))
    await asyncio.sleep(0.05)
    await page.send(uc.cdp.input_.dispatch_key_event(
        type_="keyUp",
        key=key,
        code=code,
        windows_virtual_key_code=keycode
    ))


async def wait_for_captcha(page):
    """CAPTCHA varsa kullanıcının geçmesini bekle"""
    for _ in range(60):
        url = await page.evaluate("window.location.href")
        text = await page.evaluate("document.body.innerText.substring(0, 500)")
        
        if 'hloading' not in str(url) and 'basılı' not in str(text).lower():
            return True
        
        print("   ⏳ CAPTCHA bekleniyor... (Butona basılı tut!)")
        await asyncio.sleep(2)
    
    return False


async def check_rate_limit(page) -> bool:
    """Rate limit veya ban kontrolü"""
    text = await page.evaluate("document.body.innerText")
    text_lower = str(text).lower()
    
    rate_limit_indicators = [
        'hakkınızı doldurdunuz',
        '24 saat',
        'çok fazla',
        'too many',
        'rate limit',
        'blocked',
        'banned',
        'engellendi'
    ]
    
    for indicator in rate_limit_indicators:
        if indicator in text_lower:
            return True
    
    return False


async def login_with_account(page, account: dict) -> bool:
    """
    Belirtilen hesapla login yap.
    
    Returns:
        True: Login başarılı
        False: Login başarısız
    """
    email = account['email']
    password = account['password']
    
    print(f"\n🔐 Login yapılıyor: {email}")
    
    # Login sayfasına git
    await page.get("https://secure.sahibinden.com/giris")
    await asyncio.sleep(3)
    await wait_for_captcha(page)
    
    # Email alanı
    email_input = await page.select('input[type="email"], input[name="username"], #username')
    if not email_input:
        print("   ❌ Email alanı bulunamadı!")
        return False
    
    await email_input.click()
    await asyncio.sleep(0.5)
    await type_like_human(page, email)
    await asyncio.sleep(0.5)
    
    # Tab ile şifre alanına
    await press_key(page, "Tab", "Tab", 9)
    await asyncio.sleep(0.3)
    
    # Şifre
    await type_like_human(page, password)
    await asyncio.sleep(0.5)
    
    # Giriş butonuna tıkla
    clicked = False
    try:
        btn = await page.find("E-posta ile giriş yap", timeout=3)
        if btn:
            await btn.click()
            clicked = True
    except:
        pass
    
    if not clicked:
        try:
            btn = await page.select('button[type="submit"]')
            if btn:
                await btn.click()
                clicked = True
        except:
            pass
    
    if not clicked:
        await press_key(page, "Enter", "Enter", 13)
    
    await asyncio.sleep(5)
    await wait_for_captcha(page)
    
    # Rate limit kontrolü
    if await check_rate_limit(page):
        print(f"   🟠 Rate limit algılandı! Hesap limited olarak işaretleniyor...")
        manager.mark_as_limited(email, hours=24)
        return False
    
    # 2FA kontrolü
    url = await page.evaluate("window.location.href")
    text = await page.evaluate("document.body.innerText.substring(0, 1000)")
    
    is_2fa = 'dogrulama' in str(url).lower() or \
             'asamali' in str(url).lower() or \
             'verification' in str(url).lower() or \
             'onay' in str(text).lower() or \
             'doğrulama kod' in str(text).lower()
    
    if is_2fa:
        print("   📧 2FA gerekiyor...")
        
        # Kendi domain'den kod al
        code = get_2fa_from_domain(email, max_wait=90)
        
        if code:
            print(f"   🔢 Kod: {code}")
            
            # Kod girişi
            result = await page.evaluate(f"""
                (() => {{
                    const code = "{code}";
                    let inputs = document.querySelectorAll('input[maxlength="1"]');
                    if (inputs.length === 0) inputs = document.querySelectorAll('input[type="tel"]');
                    
                    const codeInputs = Array.from(inputs).slice(0, 6);
                    for (let i = 0; i < Math.min(code.length, codeInputs.length); i++) {{
                        codeInputs[i].focus();
                        codeInputs[i].value = code[i];
                        codeInputs[i].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                    return codeInputs.map(i => i.value).join('');
                }})()
            """)
            
            # Doğrula butonu
            await asyncio.sleep(1)
            try:
                btn = await page.find("Doğrula", timeout=3)
                if btn:
                    await btn.click()
            except:
                await press_key(page, "Enter", "Enter", 13)
            
            await asyncio.sleep(5)
            await wait_for_captcha(page)
            
            # Rate limit kontrolü (2FA sonrası)
            if await check_rate_limit(page):
                print(f"   🟠 2FA rate limit! Hesap limited olarak işaretleniyor...")
                manager.mark_as_limited(email, hours=24)
                return False
        else:
            print("   ❌ 2FA kodu alınamadı!")
            return False
    
    # Login başarı kontrolü
    url = await page.evaluate("window.location.href")
    is_still_login = 'giris' in str(url).lower() or 'login' in str(url).lower() or 'dogrulama' in str(url).lower()
    
    if is_still_login:
        print("   ❌ Login başarısız!")
        return False
    
    print("   ✅ Login başarılı!")
    
    # Hesabı güncelle
    manager.update_account(email, 
                          last_used=datetime.now().isoformat(),
                          status="active")
    
    # Cookie kaydet
    cookies_str = await page.evaluate("document.cookie")
    manager.update_account(email, cookies=cookies_str)
    
    return True


async def ensure_logged_in(page) -> dict | None:
    """
    Giriş yapılmış olduğundan emin ol.
    Gerekirse hesap rotasyonu yap.
    
    Returns:
        Aktif hesap bilgisi veya None
    """
    # Önce aktif hesabı dene
    account = manager.get_active_account()
    
    if account and account['status'] in ['active', 'verified']:
        # Mevcut cookie'leri dene
        if account.get('cookies'):
            print(f"\n🍪 Kaydedilmiş cookie'ler deneniyor: {account['email']}")
            # Cookie'leri yükle
            try:
                for cookie_str in account['cookies'].split(';'):
                    if '=' in cookie_str:
                        name, val = cookie_str.strip().split('=', 1)
                        await page.evaluate(f'document.cookie = "{name}={val}; domain=.sahibinden.com; path=/"')
            except:
                pass
            
            # Ana sayfayı yenile ve kontrol et
            await page.get("https://www.sahibinden.com")
            await asyncio.sleep(2)
            
            # Login durumu kontrolü
            text = await page.evaluate("document.body.innerText.substring(0, 500)")
            if 'hesabım' in str(text).lower() or 'çıkış' in str(text).lower():
                print("   ✅ Cookie'ler geçerli!")
                return account
        
        # Cookie geçersiz, login dene
        if await login_with_account(page, account):
            return account
    
    # Aktif hesap yok veya başarısız, rotasyon yap
    print("\n🔄 Hesap rotasyonu yapılıyor...")
    
    max_attempts = len(manager.list_accounts())
    for attempt in range(max_attempts):
        account = manager.rotate_account()
        
        if not account:
            print("   ❌ Kullanılabilir hesap kalmadı!")
            return None
        
        print(f"\n   [{attempt+1}/{max_attempts}] Denenen hesap: {account['email']}")
        
        if await login_with_account(page, account):
            manager.set_active_account(account['email'])
            return account
        
        # Kısa bekleme
        await asyncio.sleep(random.randint(5, 10))
    
    return None


async def scrape_with_retry(page, scrape_func, *args, max_retries=3, **kwargs):
    """
    Rate limit durumunda hesap değiştirerek tekrar dene.
    """
    for retry in range(max_retries):
        try:
            result = await scrape_func(page, *args, **kwargs)
            return result
        except Exception as e:
            if 'rate limit' in str(e).lower() or await check_rate_limit(page):
                print(f"\n🟠 Rate limit algılandı (deneme {retry+1}/{max_retries})")
                
                # Mevcut hesabı limitli olarak işaretle
                current = manager.get_active_account()
                if current:
                    manager.mark_as_limited(current['email'])
                
                # Yeni hesap bul
                new_account = await ensure_logged_in(page)
                if not new_account:
                    print("❌ Kullanılabilir hesap kalmadı!")
                    raise Exception("No available accounts")
                
                await asyncio.sleep(random.randint(10, 20))
            else:
                raise e
    
    raise Exception(f"Failed after {max_retries} retries")


async def main():
    print("=" * 60)
    print("🏠 SAHİBİNDEN SCRAPER v3 - MULTI ACCOUNT")
    print("=" * 60)
    
    # Hesap durumunu kontrol et
    stats = manager.get_stats()
    print(f"\n📊 Hesap Durumu:")
    print(f"   Toplam: {stats['total']}")
    print(f"   Kullanılabilir: {stats['active'] + stats['verified']}")
    print(f"   Limited: {stats['limited']}")
    
    if stats['total'] == 0:
        print("\n❌ Hiç hesap yok! Önce hesap oluşturun:")
        print("   python account_manager.py --create 3")
        return
    
    if stats['active'] + stats['verified'] == 0:
        print("\n⚠️ Kullanılabilir hesap yok! Tüm hesaplar limited/banned.")
        print("   Yeni hesap oluşturun: python account_manager.py --create 1")
        return
    
    # Browser başlat
    print("\n🚀 Browser başlatılıyor...")
    browser = await uc.start(headless=False)
    page = await browser.get("https://www.sahibinden.com")
    await asyncio.sleep(3)
    
    # Çerez popup
    try:
        btn = await page.find("Kabul Et", timeout=3)
        if btn:
            await btn.click()
            print("🍪 Çerez kabul edildi")
    except:
        pass
    
    await wait_for_captcha(page)
    
    # Login sağla
    account = await ensure_logged_in(page)
    if not account:
        print("\n❌ Giriş yapılamadı!")
        input(">>> Manuel login yap ve ENTER bas: ")
    else:
        print(f"\n✅ Aktif hesap: {account['email']}")
    
    # ========== SCRAPING ==========
    print("\n" + "=" * 60)
    print("🏪 MAĞAZA SCRAPING")
    print("=" * 60)
    
    store_url = "https://kellerwillamskarma.sahibinden.com"
    print(f"\n📍 Mağaza: {store_url}")
    
    await page.get(store_url)
    await asyncio.sleep(3)
    await wait_for_captcha(page)
    
    # Rate limit kontrolü
    if await check_rate_limit(page):
        print("🟠 Rate limit algılandı, hesap değiştiriliyor...")
        current = manager.get_active_account()
        if current:
            manager.mark_as_limited(current['email'])
        
        account = await ensure_logged_in(page)
        if account:
            await page.get(store_url)
            await asyncio.sleep(3)
    
    # İlan linklerini topla
    print("\n📋 İlan linkleri toplanıyor...")
    all_urls = []
    
    for page_num in range(10):
        offset = page_num * 50
        url = f"{store_url}?pagingOffset={offset}" if page_num > 0 else store_url
        
        print(f"\n   Sayfa {page_num + 1}: {url[:60]}...")
        await page.get(url)
        await asyncio.sleep(3)
        await wait_for_captcha(page)
        
        # Rate limit kontrolü
        if await check_rate_limit(page):
            print("   🟠 Rate limit! Hesap değiştiriliyor...")
            current = manager.get_active_account()
            if current:
                manager.mark_as_limited(current['email'])
            
            account = await ensure_logged_in(page)
            if not account:
                print("   ❌ Hesap bulunamadı, durduruluyor.")
                break
            
            # Sayfayı tekrar yükle
            await page.get(url)
            await asyncio.sleep(3)
        
        # Linkleri çek
        links = await page.evaluate("""
            [...document.querySelectorAll('a[href*="/ilan/"]')]
                .map(a => a.href)
                .filter(h => h.includes('/detay'))
        """)
        
        # Parse links
        new_links = []
        if isinstance(links, list):
            for item in links:
                if isinstance(item, dict) and 'value' in item:
                    new_links.append(item['value'])
                elif isinstance(item, str):
                    new_links.append(item)
        
        if not new_links:
            print(f"   Son sayfa veya boş")
            break
        
        all_urls.extend(new_links)
        print(f"   ✓ {len(new_links)} link bulundu (Toplam: {len(set(all_urls))})")
        
        await asyncio.sleep(random.uniform(3, 5))
    
    all_urls = list(set(all_urls))
    print(f"\n📋 Toplam {len(all_urls)} benzersiz ilan")
    
    # URL'leri kaydet
    with open(DATA_DIR / "urls.json", 'w') as f:
        json.dump(all_urls, f, indent=2)
    
    # İlan detayları
    if all_urls:
        print("\n" + "=" * 60)
        print("📄 İLAN DETAYLARI")
        print("=" * 60)
        
        listings = []
        rate_limit_count = 0
        
        for i, url in enumerate(all_urls):
            print(f"\n[{i+1}/{len(all_urls)}] {url[:50]}...")
            
            await page.get(url)
            await asyncio.sleep(2)
            await wait_for_captcha(page)
            
            # Rate limit kontrolü
            if await check_rate_limit(page):
                rate_limit_count += 1
                print(f"   🟠 Rate limit! ({rate_limit_count}. kez)")
                
                current = manager.get_active_account()
                if current:
                    manager.mark_as_limited(current['email'])
                
                account = await ensure_logged_in(page)
                if not account:
                    print("   ❌ Hesap bulunamadı, durduruluyor.")
                    break
                
                # Sayfayı tekrar yükle
                await page.get(url)
                await asyncio.sleep(2)
                rate_limit_count = 0
            
            data = await page.evaluate("""
                (() => ({
                    title: document.querySelector('h1')?.innerText || '',
                    price: document.querySelector('.classifiedInfo h3')?.innerText || '',
                    location: document.querySelector('.classifiedInfo h2')?.innerText || '',
                    description: document.querySelector('#classifiedDescription')?.innerText || ''
                }))()
            """)
            
            # Parse
            listing = {}
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, list) and len(item) == 2:
                        k, v = item
                        listing[k] = v.get('value', '') if isinstance(v, dict) else v
            else:
                listing = data
            
            listing['url'] = url
            listing['scraped_at'] = datetime.now().isoformat()
            listing['account_used'] = manager.get_active_account()['email'] if manager.get_active_account() else 'unknown'
            listings.append(listing)
            
            print(f"   ✅ {listing.get('title', 'N/A')[:40]}")
            
            # Her 10 ilandan bir kaydet
            if len(listings) % 10 == 0:
                with open(DATA_DIR / "listings.json", 'w', encoding='utf-8') as f:
                    json.dump(listings, f, indent=2, ensure_ascii=False)
                print(f"\n   💾 {len(listings)} ilan kaydedildi (ara kayıt)")
            
            await asyncio.sleep(random.uniform(2, 4))
        
        # Final kayıt
        with open(DATA_DIR / "listings.json", 'w', encoding='utf-8') as f:
            json.dump(listings, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 {len(listings)} ilan kaydedildi")
    
    # Final istatistikler
    print("\n" + "=" * 60)
    print("📊 FİNAL İSTATİSTİKLER")
    print("=" * 60)
    
    stats = manager.get_stats()
    print(f"   Toplam hesap: {stats['total']}")
    print(f"   Active: {stats['active']}")
    print(f"   Limited: {stats['limited']}")
    print(f"   Banned: {stats['banned']}")
    
    print("\n✅ TAMAMLANDI")
    
    input("\nENTER ile browser'ı kapat: ")
    browser.stop()


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
