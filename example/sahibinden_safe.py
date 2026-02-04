"""
Sahibinden.com Safe Scraper
============================
- 403 engelini aşmak için SADECE nodriver (browser) kullanır
- curl_cffi yok - tüm istekler browser üzerinden
- Random delay ile insan gibi davranış
- Cookie persistence
- Otomatik login + Gmail'den 2FA kodu okuma
"""
import asyncio
import json
import random
import os
import re
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from pathlib import Path
import time

import nodriver as uc

# Login bilgileri
CREDENTIALS = {
    "email": "wwazder@gmail.com",
    "password": "BombaYagiyo31"
}

# Gmail IMAP - 2FA kodunu otomatik almak için
GMAIL_IMAP = {
    "email": "wwazder@gmail.com",
    "app_password": "rxlkdfxwbhlanqhy"  # boşluksuz
}

# Dosya yolları
COOKIE_FILE = Path(__file__).parent / "sahibinden_cookies.json"
DATA_DIR = Path(__file__).parent / "kellerwilliams_data"
DATA_DIR.mkdir(exist_ok=True)


class SafeScraper:
    """403'ü aşmak için güvenli scraper - sadece browser kullanır"""
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.cookies = {}
    
    def get_2fa_code_from_gmail(self, max_wait=60) -> str:
        """Gmail'den Sahibinden 2FA kodunu oku"""
        print("📧 Gmail'den 2FA kodu bekleniyor...")
        
        start_time = time.time()
        seen_codes = set()  # Daha önce görülen kodları takip et
        
        while time.time() - start_time < max_wait:
            try:
                # Gmail IMAP'a bağlan
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(GMAIL_IMAP["email"], GMAIL_IMAP["app_password"])
                mail.select("INBOX")
                
                # Son 1 dakikadaki UNREAD Sahibinden maillerini ara
                # NOT: "sahibinden" kelimesini FROM veya SUBJECT'te ara
                _, messages = mail.search(None, '(UNSEEN FROM "sahibinden")')
                
                if not messages[0]:
                    # UNSEEN bulamazsan son 2 dakikadaki tüm Sahibinden maillerine bak
                    date_since = (datetime.now() - timedelta(minutes=2)).strftime("%d-%b-%Y")
                    _, messages = mail.search(None, f'(FROM "sahibinden" SINCE "{date_since}")')
                
                if messages[0]:
                    # En son maili al
                    latest_id = messages[0].split()[-1]
                    _, msg_data = mail.fetch(latest_id, "(RFC822)")
                    
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            # Mail tarihini kontrol et
                            date_str = msg.get('Date', '')
                            
                            # Mail içeriğini al
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                        break
                                    elif part.get_content_type() == "text/html":
                                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            else:
                                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                            
                            # 6 haneli kodu bul (4-6 haneli olabilir)
                            codes = re.findall(r'\b(\d{4,6})\b', body)
                            for code in codes:
                                # Daha önce görülmemiş kodu döndür
                                if code not in seen_codes and len(code) >= 4:
                                    print(f"   ✅ Yeni kod bulundu: {code}")
                                    mail.logout()
                                    return code
                                else:
                                    seen_codes.add(code)
                
                mail.logout()
                
            except Exception as e:
                print(f"   ⚠️ Gmail hatası: {e}")
            
            print(f"   ⏳ Yeni mail bekleniyor... ({int(time.time() - start_time)}s)")
            time.sleep(3)
        
        print("   ❌ Kod bulunamadı, manuel giriş gerekiyor")
        return None
        
    async def type_like_human(self, text: str, delay_min=0.05, delay_max=0.15):
        """İnsan gibi tek tek karakter yaz - CDP ile gerçek klavye eventi"""
        for char in text:
            # insertText kullan - özel karakterler için daha güvenilir
            await self.page.send(uc.cdp.input_.insert_text(text=char))
            # İnsan gibi rastgele gecikme
            await asyncio.sleep(random.uniform(delay_min, delay_max))
    
    async def random_delay(self, min_sec=2, max_sec=5):
        """İnsan gibi rastgele bekleme"""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
        
    async def start(self):
        """Browser başlat"""
        print("=" * 60)
        print("🏠 SAHİBİNDEN SAFE SCRAPER (Browser Only)")
        print("   403 koruması için sadece browser kullanılıyor")
        print("=" * 60)
        
        # Browser'ı daha gerçekçi ayarlarla başlat
        self.browser = await uc.start(
            headless=False,
            browser_args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--no-default-browser-check',
            ]
        )
        
        print("\n🌐 Sahibinden.com'a bağlanılıyor...")
        self.page = await self.browser.get("https://www.sahibinden.com")
        await asyncio.sleep(3)
        
        # Press & Hold CAPTCHA kontrolü
        await self._handle_press_hold_captcha()
        
        # Çerez popup'ını kapat
        await self._close_cookie_popup()
        
        # Cookie'leri yükle veya login yap
        if await self._load_and_verify_cookies():
            print("✅ Kaydedilmiş session aktif!")
        else:
            await self._manual_login()
        
        return True
    
    async def _handle_press_hold_captcha(self):
        """Press and Hold CAPTCHA'yı geç - kullanıcıdan manuel müdahale ister"""
        for attempt in range(3):
            try:
                current_url = await self.page.evaluate("window.location.href")
                page_text = await self.page.evaluate("document.body.innerText.substring(0, 1000)")
                
                # CAPTCHA sayfası mı kontrol et
                is_captcha = 'hloading' in str(current_url) or \
                             'basılı' in str(page_text).lower() or \
                             'tutunuz' in str(page_text).lower() or \
                             'hold' in str(page_text).lower() or \
                             'tarayıcınızı kontrol' in str(page_text).lower()
                
                if not is_captcha:
                    return True  # CAPTCHA yok, devam et
                
                print(f"\n   🤖 CAPTCHA tespit edildi!")
                print("   👆 Lütfen tarayıcıda 'Basılı Tutunuz' butonuna basılı tut!")
                print("   ⏳ CAPTCHA geçene kadar bekliyorum...")
                
                # Kullanıcının CAPTCHA'yı manuel geçmesini bekle
                for wait in range(60):  # Max 120 saniye bekle
                    await asyncio.sleep(2)
                    
                    new_url = await self.page.evaluate("window.location.href")
                    
                    # CAPTCHA geçildi mi?
                    if 'hloading' not in str(new_url):
                        print("   ✅ CAPTCHA geçildi!")
                        await asyncio.sleep(2)
                        return True
                    
                    if wait % 10 == 0 and wait > 0:
                        print(f"   ⏳ Hala bekliyorum... ({wait * 2}s)")
                
            except Exception as e:
                print(f"   ⚠️ CAPTCHA kontrol hatası: {e}")
        
        return False
    
    async def _close_cookie_popup(self):
        """Çerez popup'ını kapat"""
        try:
            accept_btn = await self.page.find("Kabul Et", timeout=3)
            if accept_btn:
                await accept_btn.click()
                await asyncio.sleep(1)
                print("🍪 Çerez popup'ı kapatıldı")
        except:
            pass
    
    async def _load_and_verify_cookies(self) -> bool:
        """Cookie yükle ve doğrula"""
        if not COOKIE_FILE.exists():
            print("📁 Kayıtlı cookie bulunamadı")
            return False
        
        try:
            with open(COOKIE_FILE, 'r') as f:
                data = json.load(f)
            
            cookies = data.get('cookies', [])
            print(f"📁 {len(cookies)} cookie yükleniyor...")
            
            # Cookie'leri browser'a ekle
            for c in cookies:
                try:
                    await self.page.send(uc.cdp.network.set_cookie(
                        name=c['name'],
                        value=c['value'],
                        domain=c.get('domain', '.sahibinden.com'),
                        path=c.get('path', '/')
                    ))
                except:
                    pass
            
            # Sayfayı yenile
            await self.page.reload()
            await asyncio.sleep(3)
            
            # Session kontrolü
            return await self._is_logged_in()
            
        except Exception as e:
            print(f"❌ Cookie yükleme hatası: {e}")
            return False
    
    async def _is_logged_in(self) -> bool:
        """Giriş yapılmış mı kontrol et"""
        try:
            check_js = """
            (() => {
                // "Giriş Yap" butonu varsa giriş yapılmamış
                const loginText = document.body.innerText;
                if (loginText.includes('Giriş Yap') && loginText.includes('Üye Ol')) {
                    return 'not_logged_in';
                }
                // "Çıkış" veya "Hesabım" varsa giriş yapılmış
                if (loginText.includes('Çıkış') || loginText.includes('Hesabım')) {
                    return 'logged_in';
                }
                return 'unknown';
            })()
            """
            result = await self.page.evaluate(check_js)
            result_str = str(result)
            
            if 'logged_in' in result_str and 'not_' not in result_str:
                print("   ✅ Giriş yapılmış")
                return True
            elif 'not_logged_in' in result_str:
                print("   ❌ Giriş yapılmamış")
                return False
            else:
                print(f"   ⚠️ Belirsiz durum: {result_str[:50]}")
                return False
        except Exception as e:
            print(f"   Login kontrol hatası: {e}")
            return False
    
    async def _manual_login(self):
        """Otomatik login - her adımda validation ile"""
        print("\n" + "=" * 60)
        print("🔐 OTOMATİK LOGIN (Validation Enabled)")
        print("=" * 60)
        
        # ========== ADIM 0: Login sayfasına git ==========
        print("\n[ADIM 0] Login sayfasına gidiliyor...")
        await self.page.get("https://www.sahibinden.com/giris")
        await asyncio.sleep(4)
        
        # Validation 0: Login sayfasında mıyız?
        current_url = await self.page.evaluate("window.location.href")
        if 'giris' not in str(current_url).lower() and 'login' not in str(current_url).lower():
            print(f"   ❌ VALIDATION FAILED: Login sayfasına ulaşılamadı!")
            print(f"   📍 Mevcut URL: {current_url}")
            # CAPTCHA olabilir
            await self._handle_press_hold_captcha()
            # Tekrar dene
            await self.page.get("https://www.sahibinden.com/giris")
            await asyncio.sleep(3)
        
        current_url = await self.page.evaluate("window.location.href")
        print(f"   ✅ VALIDATION OK: Login sayfasındayız")
        print(f"   📍 URL: {current_url}")
        
        try:
            # ========== ADIM 1: Email alanını bul ==========
            print("\n[ADIM 1] Email alanı aranıyor...")
            
            email_input = await self.page.select('input[name="username"], input[type="email"], input[placeholder*="posta"], input[placeholder*="mail"]')
            
            # Validation 1a: Email alanı bulundu mu?
            if not email_input:
                print("   ❌ VALIDATION FAILED: Email alanı bulunamadı!")
                # Debug: Sayfadaki input'ları listele
                inputs = await self.page.evaluate("""
                    [...document.querySelectorAll('input')].map(i => ({
                        name: i.name, type: i.type, placeholder: i.placeholder, id: i.id
                    }))
                """)
                print(f"   📊 Sayfadaki input'lar: {inputs}")
                return False
            
            print("   ✅ VALIDATION OK: Email alanı bulundu")
            
            # ========== ADIM 2: Email gir ==========
            print("\n[ADIM 2] Email giriliyor...")
            await email_input.click()
            await asyncio.sleep(0.3)
            
            # Alanı temizle
            await self.page.send(uc.cdp.input_.dispatch_key_event(type_="keyDown", key="a", code="KeyA", modifiers=2))
            await self.page.send(uc.cdp.input_.dispatch_key_event(type_="keyUp", key="a", code="KeyA"))
            await asyncio.sleep(0.1)
            await self.page.send(uc.cdp.input_.dispatch_key_event(type_="keyDown", key="Backspace", code="Backspace"))
            await self.page.send(uc.cdp.input_.dispatch_key_event(type_="keyUp", key="Backspace", code="Backspace"))
            await asyncio.sleep(0.3)
            
            # Email yaz
            await self.type_like_human(CREDENTIALS["email"])
            await asyncio.sleep(0.5)
            
            # Validation 2: Email doğru girildi mi?
            email_value = await self.page.evaluate("""
                document.querySelector('input[name="username"], input[type="email"]')?.value || ''
            """)
            email_value = str(email_value).replace("{'type': 'string', 'value': '", "").replace("'}", "")
            
            if CREDENTIALS["email"] not in email_value:
                print(f"   ❌ VALIDATION FAILED: Email doğru girilmedi!")
                print(f"   📊 Beklenen: {CREDENTIALS['email']}")
                print(f"   📊 Girilen: {email_value}")
                return False
            
            print(f"   ✅ VALIDATION OK: Email doğru girildi: {email_value}")
            
            # ========== ADIM 3: Şifre alanına geç ==========
            print("\n[ADIM 3] Şifre alanına geçiliyor (Tab)...")
            await self.page.send(uc.cdp.input_.dispatch_key_event(type_="keyDown", key="Tab", code="Tab"))
            await self.page.send(uc.cdp.input_.dispatch_key_event(type_="keyUp", key="Tab", code="Tab"))
            await asyncio.sleep(0.5)
            
            # Validation 3: Şifre alanına focus geldi mi?
            focused_type = await self.page.evaluate("""
                document.activeElement?.type || document.activeElement?.tagName || 'unknown'
            """)
            focused_type = str(focused_type)
            
            if 'password' not in focused_type.lower():
                print(f"   ⚠️ VALIDATION WARNING: Focus password alanında olmayabilir")
                print(f"   📊 Focus: {focused_type}")
                # Manuel olarak şifre alanına tıkla
                password_input = await self.page.select('input[type="password"]')
                if password_input:
                    await password_input.click()
                    await asyncio.sleep(0.3)
                    print("   🔄 Şifre alanına manuel tıklandı")
            else:
                print(f"   ✅ VALIDATION OK: Şifre alanında focus var")
            
            # ========== ADIM 4: Şifre gir ==========
            print("\n[ADIM 4] Şifre giriliyor...")
            await self.type_like_human(CREDENTIALS["password"])
            await asyncio.sleep(0.5)
            
            # Validation 4: Şifre girildi mi?
            password_value = await self.page.evaluate("""
                document.querySelector('input[type="password"]')?.value?.length || 0
            """)
            password_len = int(str(password_value).replace("{'type': 'number', 'value': ", "").replace("}", ""))
            
            if password_len < 3:
                print(f"   ❌ VALIDATION FAILED: Şifre girilmedi veya çok kısa!")
                print(f"   📊 Şifre uzunluğu: {password_len}")
                return False
            
            print(f"   ✅ VALIDATION OK: Şifre girildi ({password_len} karakter)")
            
            # ========== ADIM 5: Giriş butonuna bas ==========
            print("\n[ADIM 5] Giriş butonuna basılıyor...")
            
            # URL'yi kaydet (karşılaştırma için)
            url_before = await self.page.evaluate("window.location.href")
            
            # Enter tuşuna bas
            await self.page.send(uc.cdp.input_.dispatch_key_event(
                type_="keyDown", key="Enter", code="Enter",
                windows_virtual_key_code=13, native_virtual_key_code=13
            ))
            await self.page.send(uc.cdp.input_.dispatch_key_event(
                type_="keyUp", key="Enter", code="Enter"
            ))
            print("   ⏳ Enter tuşuna basıldı, sayfa yükleniyor...")
            
            await asyncio.sleep(6)
            
            # Validation 5: URL değişti mi?
            url_after = await self.page.evaluate("window.location.href")
            
            if str(url_before) == str(url_after):
                print(f"   ⚠️ VALIDATION WARNING: URL değişmedi!")
                print(f"   📍 URL: {url_after}")
                
                # Hata mesajı var mı kontrol et
                error_msg = await self.page.evaluate("""
                    document.querySelector('.error, .alert, [class*="error"], [class*="alert"]')?.innerText || ''
                """)
                if error_msg:
                    print(f"   ❌ Hata mesajı: {error_msg}")
                
                # Belki giriş butonu var hala - tıklamayı dene
                print("   🔄 Giriş butonuna tıklamayı deniyorum...")
                login_btn = await self.page.find("E-posta ile giriş yap", timeout=3)
                if login_btn:
                    await login_btn.click()
                    await asyncio.sleep(5)
                    url_after = await self.page.evaluate("window.location.href")
            
            print(f"   📍 Yeni URL: {url_after}")
            
            # CAPTCHA kontrolü
            if 'hloading' in str(url_after):
                print("   ⚠️ CAPTCHA tespit edildi!")
                await self._handle_press_hold_captcha()
                url_after = await self.page.evaluate("window.location.href")
            
            # ========== ADIM 6: 2FA kontrolü ==========
            print("\n[ADIM 6] 2FA kontrolü yapılıyor...")
            page_text = await self.page.evaluate("document.body.innerText")
            
            is_2fa = 'dogrulama' in str(url_after).lower() or \
                     'verification' in str(url_after).lower() or \
                     'onay kodu' in str(page_text).lower() or \
                     'doğrulama kodu' in str(page_text).lower()
            
            is_still_login = 'giris' in str(url_after).lower() or 'login' in str(url_after).lower()
            
            if is_still_login and not is_2fa:
                print("   ❌ VALIDATION FAILED: Hala login sayfasındayız!")
                print("   📊 Giriş başarısız olmuş olabilir")
                
                # Manuel müdahale iste
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: input(">>> Manuel giriş yapıp ENTER'a basın: "))
                url_after = await self.page.evaluate("window.location.href")
            
            if is_2fa:
                
                print("\n" + "=" * 50)
                print("📧 EMAIL 2FA - OTOMATİK KOD OKUMA")
                print("=" * 50)
                
                # Gmail'den kodu al
                code = self.get_2fa_code_from_gmail(max_wait=90)
                
                if code:
                    # Kodu otomatik gir
                    print(f"🔢 Kod giriliyor: {code}")
                    code_input = await self.page.select('input[name="code"], input[type="text"], input[type="tel"], input[type="number"]')
                    if code_input:
                        await code_input.click()
                        await asyncio.sleep(0.5)
                        await code_input.send_keys(code)
                        await asyncio.sleep(1)
                        
                        # Doğrula butonuna tıkla
                        verify_btn = await self.page.select('button[type="submit"], input[type="submit"]')
                        if verify_btn:
                            await verify_btn.click()
                        else:
                            verify_btn = await self.page.find("Doğrula", timeout=3)
                            if verify_btn:
                                await verify_btn.click()
                        
                        await asyncio.sleep(3)
                        print("✅ 2FA kodu girildi!")
                        
                        # 2FA sonrası CAPTCHA kontrolü
                        await self._handle_press_hold_captcha()
                else:
                    # Manuel giriş
                    print("""
   ❌ Otomatik kod alınamadı!
   
   Lütfen:
   1. Email'ini kontrol et
   2. Kodu tarayıcıya gir
   3. ENTER'a bas
""")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: input(">>> ENTER: "))
                    
                    # Manuel 2FA sonrası da CAPTCHA kontrolü
                    await self._handle_press_hold_captcha()
            
            # Login sonrası CAPTCHA kontrolü
            await self._handle_press_hold_captcha()
            
            # Ana sayfaya git
            current_url = await self.page.evaluate("window.location.href")
            if 'sahibinden.com' in str(current_url) and 'giris' not in str(current_url).lower():
                print("✅ Login başarılı, ana sayfaya geçiliyor...")
            
            await self.page.get("https://www.sahibinden.com")
            await asyncio.sleep(3)
            
            # Ana sayfa sonrası da CAPTCHA kontrolü
            await self._handle_press_hold_captcha()
            
        except Exception as e:
            print(f"❌ Login hatası: {e}")
            import traceback
            traceback.print_exc()
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: input(">>> Manuel login yapıp ENTER'a basın: "))
        
        await self._save_cookies()
        print("✅ Session kaydedildi!")
    
    async def _save_cookies(self):
        """Cookie kaydet"""
        try:
            cookie_str = await self.page.evaluate("document.cookie")
            cookies = []
            for item in str(cookie_str).split(';'):
                if '=' in item:
                    name, value = item.strip().split('=', 1)
                    cookies.append({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.sahibinden.com',
                        'path': '/'
                    })
            
            with open(COOKIE_FILE, 'w') as f:
                json.dump({
                    'cookies': cookies,
                    'saved_at': datetime.now().isoformat()
                }, f, indent=2)
            
            print(f"💾 {len(cookies)} cookie kaydedildi")
        except Exception as e:
            print(f"❌ Cookie kaydetme hatası: {e}")
    
    async def get_page_safe(self, url: str, retry=3) -> bool:
        """Güvenli sayfa yükleme - 403 ve CAPTCHA kontrolü ile"""
        for attempt in range(retry):
            try:
                await self.page.get(url)
                await self.random_delay(2, 4)
                
                # Press & Hold CAPTCHA kontrolü
                current_url = await self.page.evaluate("window.location.href")
                if 'hloading' in str(current_url):
                    await self._handle_press_hold_captcha()
                
                # 403 kontrolü
                page_text = await self.page.evaluate("document.body.innerText.substring(0, 500)")
                page_text = str(page_text).lower()
                
                if '403' in page_text or 'forbidden' in page_text or 'erişim engellendi' in page_text:
                    print(f"   ⚠️ 403 tespit edildi, {10 + attempt*5} saniye bekleniyor...")
                    await asyncio.sleep(10 + attempt * 5)
                    continue
                
                # Basılı tutunuz kontrolü
                if 'basılı tutunuz' in page_text or 'basili tutunuz' in page_text:
                    await self._handle_press_hold_captcha()
                
                # Normal Captcha kontrolü
                if 'robot' in page_text or 'captcha' in page_text:
                    print("   ⚠️ Captcha tespit edildi!")
                    print("   Lütfen tarayıcıda captcha'yı çözün ve ENTER'a basın")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: input(">>> ENTER: "))
                    continue
                
                return True
                
            except Exception as e:
                print(f"   Hata: {e}, tekrar deneniyor...")
                await asyncio.sleep(5)
        
        return False
    
    async def scrape_store(self, store_url: str = "https://kellerwillamskarma.sahibinden.com"):
        """Mağazayı scrape et"""
        print(f"\n🏪 Mağaza: {store_url}")
        
        # 1. İlan URL'lerini topla
        print("\n" + "─" * 50)
        print("📋 ADIM 1: İlan URL'leri toplanıyor...")
        print("─" * 50)
        
        all_urls = []
        page_num = 0
        max_pages = 10
        
        while page_num < max_pages:
            offset = page_num * 50
            url = f"{store_url}?pagingOffset={offset}" if page_num > 0 else store_url
            
            print(f"\n📄 Sayfa {page_num + 1}...")
            
            if not await self.get_page_safe(url):
                print("   ❌ Sayfa yüklenemedi")
                break
            
            # Debug: Mevcut URL'yi kontrol et
            current_url = await self.page.evaluate("window.location.href")
            print(f"   📍 Mevcut URL: {current_url}")
            
            # Debug: Sayfa içeriği
            debug_info = await self.page.evaluate("""
                (() => {
                    return {
                        url: window.location.href,
                        title: document.title,
                        linkCount: document.querySelectorAll('a').length,
                        ilanLinks: document.querySelectorAll('a[href*="/ilan/"]').length,
                        detayLinks: [...document.querySelectorAll('a[href*="/ilan/"]')].filter(a => a.href.includes('/detay')).length,
                        bodyPreview: document.body.innerText.substring(0, 200)
                    };
                })()
            """)
            print(f"   📊 Debug: {debug_info}")
            
            # CAPTCHA kontrolü
            if 'hloading' in str(current_url) or 'basılı' in str(debug_info).lower():
                print("   ⚠️ CAPTCHA tespit edildi!")
                await self._handle_press_hold_captcha()
                continue
            
            # İlan linklerini çek
            links = await self.page.evaluate("""
                [...document.querySelectorAll('a[href*="/ilan/"]')]
                    .map(a => a.href)
                    .filter(h => h.includes('/detay'))
            """)
            
            # Nodriver value extraction
            if isinstance(links, list):
                for item in links:
                    if isinstance(item, dict) and 'value' in item:
                        all_urls.append(item['value'])
                    elif isinstance(item, str):
                        all_urls.append(item)
            
            unique_count = len(set(all_urls))
            print(f"   ✓ Toplam {unique_count} benzersiz URL")
            
            # Son sayfaya ulaştıysak dur
            current_page_links = await self.page.evaluate("""
                document.querySelectorAll('a[href*="/ilan/"]').length
            """)
            if isinstance(current_page_links, dict):
                current_page_links = current_page_links.get('value', 0)
            
            if int(current_page_links) < 5:
                print("   Son sayfaya ulaşıldı")
                break
            
            page_num += 1
            await self.random_delay(3, 6)  # Sayfalar arası bekleme
        
        all_urls = list(set(all_urls))
        print(f"\n📋 Toplam {len(all_urls)} ilan bulundu")
        
        # URL'leri kaydet
        with open(DATA_DIR / "listing_urls.json", 'w') as f:
            json.dump(all_urls, f, indent=2)
        
        # 2. Her ilanın detayını çek
        print("\n" + "─" * 50)
        print("📄 ADIM 2: İlan detayları çekiliyor...")
        print("─" * 50)
        
        all_listings = []
        
        for i, url in enumerate(all_urls):
            print(f"\n[{i+1}/{len(all_urls)}] {url[:60]}...")
            
            listing = await self.scrape_listing(url)
            if listing:
                all_listings.append(listing)
                print(f"   ✓ {listing.get('title', 'N/A')[:40]}")
                print(f"   💰 {listing.get('price', 'N/A')} | 📷 {len(listing.get('images', []))} foto")
            else:
                print("   ❌ Çekilemedi")
            
            # Her 10 ilanda kaydet
            if (i + 1) % 10 == 0:
                self._save_listings(all_listings)
                print(f"\n💾 {len(all_listings)} ilan kaydedildi")
            
            # Random bekleme
            await self.random_delay(3, 7)
        
        # Final kaydet
        self._save_listings(all_listings)
        
        print("\n" + "=" * 60)
        print(f"✅ TAMAMLANDI: {len(all_listings)} ilan çekildi")
        print(f"📁 Veri: {DATA_DIR / 'listings_full.json'}")
        print("=" * 60)
        
        return all_listings
    
    async def scrape_listing(self, url: str) -> dict:
        """Tek ilan detayını çek"""
        try:
            if not await self.get_page_safe(url):
                return None
            
            # Tüm verileri JS ile çek
            data_js = """
            (() => {
                const data = {};
                
                // URL ve ID
                data.url = window.location.href;
                data.id = window.location.href.match(/-(\\d+)\\/detay/)?.[1] || '';
                
                // Başlık
                data.title = document.querySelector('h1')?.innerText?.trim() || '';
                
                // Fiyat
                const priceEl = document.querySelector('.classifiedInfo h3, .price-container, [class*="price"] h3');
                data.price = priceEl?.innerText?.trim() || '';
                
                // Konum
                data.location = document.querySelector('.classifiedInfo h2, .location')?.innerText?.trim() || '';
                
                // Açıklama
                data.description = document.querySelector('#classifiedDescription, .classifiedDescription')?.innerText?.trim() || '';
                
                // Özellikler tablosu
                data.specs = {};
                document.querySelectorAll('.classifiedInfoList li, .classified-info-list li').forEach(li => {
                    const strong = li.querySelector('strong');
                    const span = li.querySelector('span');
                    if (strong && span) {
                        const key = strong.innerText.replace(':', '').trim();
                        const val = span.innerText.trim();
                        if (key && val) data.specs[key] = val;
                    }
                });
                
                // Fotoğraflar - birden fazla yöntem
                data.images = [];
                
                // Yöntem 1: Galeri thumbnail'ları
                document.querySelectorAll('.classifiedDetailPhotos img, .thumbs img').forEach(img => {
                    let src = img.src || img.dataset.src || '';
                    if (src && src.includes('shbdn')) {
                        // Küçük resmi büyük resme çevir
                        src = src.replace(/_t\\.(jpg|png|jpeg)/i, '.$1')
                                 .replace(/\\/s\\//g, '/x/');
                        data.images.push(src);
                    }
                });
                
                // Yöntem 2: Data attribute'lardan
                document.querySelectorAll('[data-large-img], [data-original]').forEach(el => {
                    const src = el.dataset.largeImg || el.dataset.original;
                    if (src && !data.images.includes(src)) {
                        data.images.push(src);
                    }
                });
                
                // Yöntem 3: Tüm büyük resimler
                document.querySelectorAll('img').forEach(img => {
                    const src = img.src;
                    if (src && src.includes('shbdn') && src.includes('/x/') && !data.images.includes(src)) {
                        data.images.push(src);
                    }
                });
                
                // Satıcı bilgisi
                data.seller = document.querySelector('.username-info-area, .store-name')?.innerText?.trim() || '';
                
                // Tarih
                data.date = document.querySelector('.classifiedInfo .date, [class*="date"]')?.innerText?.trim() || '';
                
                // İlan numarası (sayfa içinde)
                const pageText = document.body.innerText;
                const ilanNo = pageText.match(/İlan No[:\\s]*(\\d+)/i)?.[1];
                if (ilanNo) data.id = ilanNo;
                
                // Breadcrumb (kategori)
                data.category = document.querySelector('.breadcrumb, .classified-category')?.innerText?.trim() || '';
                
                return data;
            })()
            """
            
            result = await self.page.evaluate(data_js)
            
            # Nodriver value extraction
            listing = {}
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, list) and len(item) == 2:
                        key, val = item
                        if isinstance(val, dict):
                            if val.get('type') == 'object':
                                # Nested object (specs)
                                listing[key] = self._extract_nested(val)
                            elif 'value' in val:
                                listing[key] = val['value']
                            else:
                                listing[key] = val
                        else:
                            listing[key] = val
            elif isinstance(result, dict):
                listing = result
            
            return listing if listing.get('title') or listing.get('id') else None
            
        except Exception as e:
            print(f"   Hata: {e}")
            return None
    
    def _extract_nested(self, val):
        """Nested object'i çıkar"""
        if isinstance(val, dict):
            if 'value' in val:
                return val['value']
            result = {}
            for k, v in val.items():
                if k not in ['type', 'subtype']:
                    result[k] = self._extract_nested(v)
            return result
        elif isinstance(val, list):
            return [self._extract_nested(v) for v in val]
        return val
    
    def _save_listings(self, listings: list):
        """Listing'leri kaydet"""
        with open(DATA_DIR / "listings_full.json", 'w', encoding='utf-8') as f:
            json.dump(listings, f, indent=2, ensure_ascii=False)
    
    async def close(self):
        """Browser'ı kapat"""
        if self.browser:
            await self.browser.stop()


async def main():
    scraper = SafeScraper()
    
    try:
        await scraper.start()
        
        # Mağazayı scrape et
        await scraper.scrape_store("https://kellerwillamskarma.sahibinden.com")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Kullanıcı tarafından durduruldu")
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
