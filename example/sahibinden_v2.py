"""
Sahibinden.com Scraper v2
=========================
- Temiz, basit, güvenilir
- Her adımda validation
- Manuel login desteği
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

# Login bilgileri
EMAIL = "wwazder@gmail.com"
PASSWORD = "BombaYagiyo31"

# Gmail IMAP
GMAIL_APP_PASSWORD = "rxlkdfxwbhlanqhy"

# Dosyalar
COOKIE_FILE = Path(__file__).parent / "sahibinden_cookies.json"
DATA_DIR = Path(__file__).parent / "kellerwilliams_data"
DATA_DIR.mkdir(exist_ok=True)


def get_2fa_from_gmail(max_wait=90):
    """Gmail'den Sahibinden 2FA kodunu oku - sadece en son okunmamış mail"""
    print("📧 Gmail'den 2FA kodu bekleniyor...")
    start = time.time()
    
    last_code = None
    
    while time.time() - start < max_wait:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(EMAIL, GMAIL_APP_PASSWORD)
            mail.select("INBOX")
            
            # Son 2 dakikadaki OKUNMAMIŞ Sahibinden mailleri
            date_since = (datetime.now() - timedelta(minutes=2)).strftime("%d-%b-%Y")
            _, messages = mail.search(None, f'(UNSEEN FROM "sahibinden" SINCE "{date_since}")')
            
            if messages[0]:
                # En son maili al
                latest_id = messages[0].split()[-1]
                _, msg_data = mail.fetch(latest_id, "(RFC822)")
                
                for part in msg_data:
                    if isinstance(part, tuple):
                        msg = email.message_from_bytes(part[1])
                        body = ""
                        if msg.is_multipart():
                            for p in msg.walk():
                                if p.get_content_type() in ["text/plain", "text/html"]:
                                    try:
                                        body = p.get_payload(decode=True).decode('utf-8', errors='ignore')
                                    except:
                                        pass
                                    if body:
                                        break
                        else:
                            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                        
                        # 6 haneli kod bul
                        matches = re.findall(r'\b(\d{6})\b', body)
                        if matches:
                            code = matches[-1]  # En son kodu al
                            if code != last_code:  # Yeni kod mu?
                                print(f"   ✅ Yeni kod bulundu: {code}")
                                mail.logout()
                                return code
                            else:
                                print(f"   ⚠️ Aynı kod: {code}, yeni mail bekleniyor...")
            
            mail.logout()
        except Exception as e:
            print(f"   Gmail hatası: {e}")
        
        elapsed = int(time.time() - start)
        print(f"   ⏳ Yeni mail bekleniyor... ({elapsed}s)")
        time.sleep(3)
    
    return None


async def type_like_human(page, text):
    """İnsan gibi tek tek karakter yaz"""
    for char in text:
        # Özel karakterler için shift gerekebilir
        if char == '@':
            # @ karakteri için
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
    for _ in range(60):  # Max 2 dakika
        url = await page.evaluate("window.location.href")
        text = await page.evaluate("document.body.innerText.substring(0, 500)")
        
        if 'hloading' not in str(url) and 'basılı' not in str(text).lower():
            return True
        
        print("   ⏳ CAPTCHA bekleniyor... (Butona basılı tut!)")
        await asyncio.sleep(2)
    
    return False


async def main():
    print("=" * 60)
    print("🏠 SAHİBİNDEN SCRAPER v2")
    print("=" * 60)
    
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
    
    # CAPTCHA kontrolü
    await wait_for_captcha(page)
    
    # ========== LOGIN ==========
    print("\n" + "=" * 60)
    print("🔐 LOGIN")
    print("=" * 60)
    
    print("\n[1/6] Login sayfasına gidiliyor...")
    await page.get("https://secure.sahibinden.com/giris")
    await asyncio.sleep(3)
    await wait_for_captcha(page)
    
    # Validation: Login sayfası mı?
    url = await page.evaluate("window.location.href")
    print(f"      📍 URL: {url}")
    if 'giris' not in str(url).lower() and 'login' not in str(url).lower():
        print("      ❌ Login sayfasına ulaşılamadı!")
        input("      >>> Manuel olarak login sayfasına git ve ENTER bas: ")
    else:
        print("      ✅ Login sayfası açıldı")
    
    # Email alanı
    print("\n[2/6] Email alanı bulunuyor...")
    email_input = await page.select('input[type="email"], input[name="username"], #username')
    if not email_input:
        print("      ❌ Email alanı bulunamadı!")
        input("      >>> Manuel olarak email gir ve ENTER bas: ")
    else:
        print("      ✅ Email alanı bulundu")
        await email_input.click()
        await asyncio.sleep(0.5)
        
        print("\n[3/6] Email yazılıyor...")
        await type_like_human(page, EMAIL)
        await asyncio.sleep(0.5)
        
        # Validation: Email yazıldı mı?
        val = await page.evaluate('document.querySelector("input[type=email], input[name=username]")?.value || ""')
        if EMAIL in str(val):
            print(f"      ✅ Email yazıldı: {val}")
        else:
            print(f"      ⚠️ Email doğrulanamadı: {val}")
    
    # Tab ile şifre alanına geç
    print("\n[4/6] Şifre alanına geçiliyor (TAB)...")
    await press_key(page, "Tab", "Tab", 9)
    await asyncio.sleep(0.5)
    
    print("\n[5/6] Şifre yazılıyor...")
    await type_like_human(page, PASSWORD)
    await asyncio.sleep(0.5)
    
    # Validation: Şifre yazıldı mı?
    val = await page.evaluate('document.querySelector("input[type=password]")?.value?.length || 0')
    if int(str(val).replace("'", "").split()[0] if isinstance(val, str) else val) > 0:
        print(f"      ✅ Şifre yazıldı ({val} karakter)")
    else:
        print("      ⚠️ Şifre doğrulanamadı")
    
    # Giriş butonuna tıkla
    print("\n[6/6] Giriş butonuna tıklanıyor...")
    await asyncio.sleep(0.5)
    
    # Butonu bul - birkaç yöntem dene
    clicked = False
    
    # Yöntem 1: "E-posta ile giriş yap" butonunu bul
    try:
        btn = await page.find("E-posta ile giriş yap", timeout=3)
        if btn:
            await btn.click()
            clicked = True
            print("      ✅ 'E-posta ile giriş yap' butonuna tıklandı")
    except:
        pass
    
    # Yöntem 2: Submit butonu
    if not clicked:
        try:
            btn = await page.select('button[type="submit"]')
            if btn:
                await btn.click()
                clicked = True
                print("      ✅ Submit butonuna tıklandı")
        except:
            pass
    
    # Yöntem 3: Giriş metni içeren buton
    if not clicked:
        try:
            btn = await page.find("Giriş", timeout=2)
            if btn:
                await btn.click()
                clicked = True
                print("      ✅ 'Giriş' butonuna tıklandı")
        except:
            pass
    
    # Yöntem 4: JavaScript ile tıkla
    if not clicked:
        try:
            result = await page.evaluate("""
                (() => {
                    // Submit butonu
                    const submitBtn = document.querySelector('button[type="submit"]');
                    if (submitBtn) {
                        submitBtn.click();
                        return 'submit_clicked';
                    }
                    
                    // Giriş yap metni içeren buton
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        if (btn.innerText.toLowerCase().includes('giriş')) {
                            btn.click();
                            return 'giris_clicked';
                        }
                    }
                    
                    // Form submit
                    const form = document.querySelector('form');
                    if (form) {
                        form.submit();
                        return 'form_submitted';
                    }
                    
                    return 'nothing_found';
                })()
            """)
            print(f"      JS sonucu: {result}")
            if 'clicked' in str(result) or 'submitted' in str(result):
                clicked = True
        except Exception as e:
            print(f"      JS hatası: {e}")
    
    # Yöntem 5: Enter tuşu (son çare)
    if not clicked:
        print("      ⚠️ Buton bulunamadı, Enter tuşu deneniyor...")
        await press_key(page, "Enter", "Enter", 13)
    
    print("⏳ Sayfa yükleniyor...")
    await asyncio.sleep(5)
    
    # CAPTCHA kontrolü
    await wait_for_captcha(page)
    
    # Validation: Login sonrası
    url = await page.evaluate("window.location.href")
    text = await page.evaluate("document.body.innerText.substring(0, 1000)")
    print(f"\n      📍 URL: {url}")
    print(f"      📄 Sayfa içeriği: {str(text)[:100]}...")
    
    # 2FA kontrolü - daha geniş pattern
    is_2fa = 'dogrulama' in str(url).lower() or \
             'asamali' in str(url).lower() or \
             'verification' in str(url).lower() or \
             'onay' in str(text).lower() or \
             'doğrulama kod' in str(text).lower() or \
             'Doğrulama Kodu' in str(text)
    
    print(f"      🔍 2FA algılandı mı: {is_2fa}")
    
    if is_2fa:
        print("\n" + "=" * 50)
        print("📧 2FA - EMAIL DOĞRULAMA")
        print("=" * 50)
        
        # Gmail'den kod al
        code = get_2fa_from_gmail(max_wait=90)
        
        if code:
            print(f"\n🔢 Kod giriliyor: {code}")
            
            # JavaScript ile execCommand kullanarak yaz - en güvenilir yöntem
            print("      📍 JavaScript execCommand yöntemi deneniyor...")
            
            result = await page.evaluate(f"""
                (() => {{
                    const code = "{code}";
                    
                    // Tüm olası input kutularını bul
                    let inputs = document.querySelectorAll('input[maxlength="1"]');
                    if (inputs.length === 0) {{
                        inputs = document.querySelectorAll('input[type="tel"]');
                    }}
                    if (inputs.length === 0) {{
                        inputs = document.querySelectorAll('.otp-input input, .code-input input, [class*="verification"] input');
                    }}
                    if (inputs.length === 0) {{
                        // Formdaki tüm inputlar
                        const form = document.querySelector('form');
                        if (form) {{
                            inputs = form.querySelectorAll('input');
                        }}
                    }}
                    
                    if (inputs.length === 0) {{
                        return 'NO_INPUTS_FOUND';
                    }}
                    
                    // Sadece tek karakterlik inputları filtrele
                    const codeInputs = Array.from(inputs).filter(inp => {{
                        return inp.maxLength === 1 || inp.type === 'tel' || inp.type === 'text';
                    }}).slice(0, 6);
                    
                    if (codeInputs.length === 0) {{
                        return 'NO_CODE_INPUTS';
                    }}
                    
                    let filled = 0;
                    for (let i = 0; i < Math.min(code.length, codeInputs.length); i++) {{
                        const inp = codeInputs[i];
                        const char = code[i];
                        
                        // Input'a focus ver
                        inp.focus();
                        inp.click();
                        
                        // Value'yu direkt set et
                        inp.value = char;
                        
                        // React/Vue gibi framework'ler için tüm eventleri tetikle
                        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        inp.dispatchEvent(new KeyboardEvent('keydown', {{ key: char, code: 'Digit' + char, keyCode: 48 + parseInt(char), bubbles: true }}));
                        inp.dispatchEvent(new KeyboardEvent('keypress', {{ key: char, code: 'Digit' + char, keyCode: 48 + parseInt(char), bubbles: true }}));
                        inp.dispatchEvent(new KeyboardEvent('keyup', {{ key: char, code: 'Digit' + char, keyCode: 48 + parseInt(char), bubbles: true }}));
                        
                        // Native value setter dene (React için)
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        nativeInputValueSetter.call(inp, char);
                        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        
                        filled++;
                    }}
                    
                    // Sonuç kontrolü
                    let values = [];
                    codeInputs.forEach(inp => values.push(inp.value));
                    return 'FILLED:' + filled + '|VALUES:' + values.join('');
                }})()
            """)
            print(f"      📊 JS sonucu: {result}")
            
            await asyncio.sleep(0.5)
            
            # Değerler girilmediyse, alternatif yöntem: Her kutuya teker teker tıklayıp yaz
            if 'VALUES:' in str(result) and str(result).split('VALUES:')[1] == '':
                print("      ⚠️ JS yöntemi başarısız, element bazlı deneniyor...")
                
                inputs = await page.select_all('input')
                for inp in inputs:
                    try:
                        maxlen = await inp.apply('(el) => el.maxLength')
                        if maxlen == 1:
                            idx = inputs.index(inp)
                            if idx < len(code):
                                await inp.click()
                                await asyncio.sleep(0.2)
                                # Mouse ile focus sonrası type
                                await page.send(uc.cdp.input_.dispatch_key_event(
                                    type_="char",
                                    text=code[idx]
                                ))
                                await asyncio.sleep(0.2)
                                print(f"         Kutu {idx+1}: {code[idx]}")
                    except Exception as e:
                        print(f"         Hata: {e}")
            
            print("      ✅ Kod girildi")
            await asyncio.sleep(2)
            
            # Validation: Kutularda değer var mı?
            filled = await page.evaluate("""
                (() => {
                    const inputs = document.querySelectorAll('input[maxlength="1"]');
                    let values = [];
                    inputs.forEach(inp => values.push(inp.value));
                    return values.join('');
                })()
            """)
            print(f"      📊 Girilen değer: {filled}")
            
            # Doğrula butonuna tıkla
            print("   🔘 Doğrula butonuna tıklanıyor...")
            clicked = False
            
            # Yöntem 1: "Doğrula" butonunu bul
            try:
                btn = await page.find("Doğrula", timeout=3)
                if btn:
                    await btn.click()
                    clicked = True
                    print("      ✅ 'Doğrula' butonuna tıklandı")
            except:
                pass
            
            # Yöntem 2: Submit butonu
            if not clicked:
                try:
                    btn = await page.select('button[type="submit"]')
                    if btn:
                        await btn.click()
                        clicked = True
                        print("      ✅ Submit butonuna tıklandı")
                except:
                    pass
            
            # Yöntem 3: JavaScript ile
            if not clicked:
                result = await page.evaluate("""
                    (() => {
                        const btn = document.querySelector('button[type="submit"]');
                        if (btn) { btn.click(); return 'clicked'; }
                        const form = document.querySelector('form');
                        if (form) { form.submit(); return 'submitted'; }
                        return 'none';
                    })()
                """)
                print(f"      JS sonucu: {result}")
            
            # Yöntem 4: Enter tuşu
            if not clicked:
                await press_key(page, "Enter", "Enter", 13)
                print("      Enter tuşuna basıldı")
            
            print("⏳ 2FA doğrulanıyor, sayfa yükleniyor...")
            await asyncio.sleep(8)
            
            # CAPTCHA kontrolü
            await wait_for_captcha(page)
        else:
            print("\n❌ Kod alınamadı!")
            input(">>> Manuel olarak kodu gir ve ENTER bas: ")
        
        await wait_for_captcha(page)
    else:
        print("      ⚠️ 2FA sayfası algılanamadı, devam ediliyor...")
    
    # Login başarılı mı? - daha kapsamlı kontrol
    await asyncio.sleep(2)
    url = await page.evaluate("window.location.href")
    print(f"\n      📍 Son URL: {url}")
    
    # 2FA veya login sayfasında değilsek başarılı
    is_still_login = 'giris' in str(url).lower() or 'login' in str(url).lower() or 'dogrulama' in str(url).lower()
    
    if is_still_login:
        print("\n❌ LOGIN BAŞARISIZ!")
        print("   Hala login sayfasındasın.")
        input(">>> Manuel login yap ve ENTER bas: ")
    else:
        print("\n✅ LOGIN BAŞARILI!")
    
    # Cookie kaydet
    print("\n💾 Cookie'ler kaydediliyor...")
    cookies_str = await page.evaluate("document.cookie")
    cookies = []
    for item in str(cookies_str).split(';'):
        if '=' in item:
            name, val = item.strip().split('=', 1)
            cookies.append({'name': name, 'value': val, 'domain': '.sahibinden.com'})
    
    with open(COOKIE_FILE, 'w') as f:
        json.dump({'cookies': cookies, 'saved_at': datetime.now().isoformat()}, f)
    print(f"   ✅ {len(cookies)} cookie kaydedildi")
    
    # ========== SCRAPING ==========
    print("\n" + "=" * 60)
    print("🏪 MAĞAZA SCRAPING")
    print("=" * 60)
    
    store_url = "https://kellerwillamskarma.sahibinden.com"
    print(f"\n📍 Mağaza: {store_url}")
    
    await page.get(store_url)
    await asyncio.sleep(3)
    await wait_for_captcha(page)
    
    # URL kontrolü
    url = await page.evaluate("window.location.href")
    print(f"   📍 Mevcut URL: {url}")
    
    if 'login' in str(url).lower() or 'giris' in str(url).lower():
        print("   ❌ Login sayfasına yönlendirildi!")
        input(">>> Manuel login yap, mağaza sayfasına git ve ENTER bas: ")
    
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
        
        await asyncio.sleep(random.uniform(2, 4))
    
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
        for i, url in enumerate(all_urls[:5]):  # Test için ilk 5
            print(f"\n[{i+1}/{len(all_urls)}] {url[:50]}...")
            
            await page.get(url)
            await asyncio.sleep(2)
            await wait_for_captcha(page)
            
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
            listings.append(listing)
            print(f"   ✅ {listing.get('title', 'N/A')[:40]}")
            
            await asyncio.sleep(random.uniform(2, 4))
        
        with open(DATA_DIR / "listings.json", 'w', encoding='utf-8') as f:
            json.dump(listings, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 {len(listings)} ilan kaydedildi")
    
    print("\n" + "=" * 60)
    print("✅ TAMAMLANDI")
    print("=" * 60)
    
    input("\nENTER ile browser'ı kapat: ")
    browser.stop()


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
