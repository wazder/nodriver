"""
Sahibinden Account Manager
==========================
Kendi domain üzerinden otomatik hesap oluşturma ve yönetim sistemi.

Özellikler:
- Rastgele email adresi oluşturma (catch-all domain)
- Otomatik Sahibinden hesap açma
- Email doğrulama kodlarını otomatik okuma
- Hesap rotasyonu (ban/limit durumunda)
- Hesap durumu takibi

Kullanım:
1. Domain bilgilerini config.py'de ayarla
2. python account_manager.py --create 5  (5 hesap oluştur)
3. python account_manager.py --list       (hesapları listele)
4. python account_manager.py --rotate     (aktif hesabı değiştir)
"""

import asyncio
import json
import random
import string
import re
import imaplib
import email
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import time
import argparse

import nodriver as uc

# ============ CONFIGURATION ============
# Cloudflare Email Routing + Gmail IMAP yapılandırması

DOMAIN_CONFIG = {
    # Domain bilgileri (Cloudflare'de kayıtlı)
    "domain": "wazder.com",
    
    # Gmail IMAP ayarları (Cloudflare catch-all → Gmail'e yönlendirme)
    # Cloudflare tüm @wazder.com maillerini Gmail'e yönlendiriyor
    # Biz de Gmail IMAP ile bu mailleri okuyoruz
    "imap_server": "imap.gmail.com",
    "imap_port": 993,
    "imap_user": "wwazder@gmail.com",  # Gmail hesabın
    "imap_password": "rxlkdfxwbhlanqhy",  # Gmail App Password (zaten var)
    
    # Opsiyonel: SMTP (email göndermek için - genelde gerekli değil)
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
}

# Hesap dosyası
ACCOUNTS_FILE = Path(__file__).parent / "sahibinden_accounts.json"

# Default şifre prefix (sonuna random eklenir)
DEFAULT_PASSWORD_PREFIX = "SahPass"


# ============ ACCOUNT DATABASE ============

class AccountManager:
    """Sahibinden hesaplarını yönetir"""
    
    def __init__(self):
        self.accounts_file = ACCOUNTS_FILE
        self.accounts = self._load_accounts()
    
    def _load_accounts(self) -> dict:
        """Hesap veritabanını yükle"""
        if self.accounts_file.exists():
            with open(self.accounts_file, 'r') as f:
                return json.load(f)
        return {
            "accounts": [],
            "active_account_index": None,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
    
    def _save_accounts(self):
        """Hesap veritabanını kaydet"""
        self.accounts["last_updated"] = datetime.now().isoformat()
        with open(self.accounts_file, 'w') as f:
            json.dump(self.accounts, f, indent=2, ensure_ascii=False)
    
    def generate_email(self) -> str:
        """Rastgele email adresi oluştur"""
        # Format: random_prefix + timestamp_hash @ domain
        prefix_options = [
            # İsim bazlı
            f"{random.choice(['ali', 'mehmet', 'ahmet', 'ayse', 'fatma', 'zeynep', 'can', 'ece', 'deniz', 'cem'])}"
            f"{random.choice(['', '_', '.'])}"
            f"{random.choice(['kaya', 'yilmaz', 'demir', 'celik', 'oz', 'ak', 'koc'])}"
            f"{random.randint(1, 999)}",
            
            # Alfanumerik
            f"user{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}",
            
            # Timestamp bazlı
            f"s{int(time.time()) % 100000}{''.join(random.choices(string.ascii_lowercase, k=4))}",
        ]
        
        prefix = random.choice(prefix_options)
        domain = DOMAIN_CONFIG["domain"]
        
        return f"{prefix}@{domain}"
    
    def generate_password(self) -> str:
        """Güçlü rastgele şifre oluştur"""
        # Format: Prefix + random chars + number + special
        chars = string.ascii_letters + string.digits
        random_part = ''.join(random.choices(chars, k=8))
        special = random.choice(['!', '@', '#', '$', '%'])
        number = str(random.randint(10, 99))
        
        return f"{DEFAULT_PASSWORD_PREFIX}{random_part}{number}{special}"
    
    def add_account(self, email: str, password: str, status: str = "pending") -> dict:
        """Yeni hesap ekle"""
        account = {
            "id": len(self.accounts["accounts"]) + 1,
            "email": email,
            "password": password,
            "status": status,  # pending, active, banned, limited, verified
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "ban_until": None,
            "cookies": None,
            "notes": ""
        }
        self.accounts["accounts"].append(account)
        self._save_accounts()
        return account
    
    def update_account(self, email: str, **kwargs):
        """Hesap bilgilerini güncelle"""
        for acc in self.accounts["accounts"]:
            if acc["email"] == email:
                acc.update(kwargs)
                self._save_accounts()
                return True
        return False
    
    def get_active_account(self) -> dict | None:
        """Aktif hesabı getir"""
        idx = self.accounts.get("active_account_index")
        if idx is not None and 0 <= idx < len(self.accounts["accounts"]):
            return self.accounts["accounts"][idx]
        return None
    
    def set_active_account(self, email: str) -> bool:
        """Aktif hesabı ayarla"""
        for i, acc in enumerate(self.accounts["accounts"]):
            if acc["email"] == email:
                self.accounts["active_account_index"] = i
                self._save_accounts()
                return True
        return False
    
    def get_available_account(self) -> dict | None:
        """Kullanılabilir bir hesap bul (banned/limited olmayanlar)"""
        now = datetime.now()
        
        for acc in self.accounts["accounts"]:
            # Aktif ve doğrulanmış hesaplar
            if acc["status"] in ["active", "verified"]:
                return acc
            
            # Limited ama süresi dolmuş
            if acc["status"] == "limited" and acc.get("ban_until"):
                ban_until = datetime.fromisoformat(acc["ban_until"])
                if now > ban_until:
                    acc["status"] = "active"
                    self._save_accounts()
                    return acc
        
        return None
    
    def rotate_account(self) -> dict | None:
        """Sonraki kullanılabilir hesaba geç"""
        current_idx = self.accounts.get("active_account_index", -1)
        accounts = self.accounts["accounts"]
        
        # Current hesabın sonrasından başla
        for i in range(len(accounts)):
            idx = (current_idx + 1 + i) % len(accounts)
            acc = accounts[idx]
            
            if acc["status"] in ["active", "verified"]:
                self.accounts["active_account_index"] = idx
                self._save_accounts()
                return acc
        
        return None
    
    def mark_as_limited(self, email: str, hours: int = 24):
        """Hesabı geçici olarak limitli olarak işaretle"""
        ban_until = datetime.now() + timedelta(hours=hours)
        self.update_account(
            email,
            status="limited",
            ban_until=ban_until.isoformat(),
            notes=f"Rate limited until {ban_until}"
        )
    
    def mark_as_banned(self, email: str):
        """Hesabı kalıcı olarak banned olarak işaretle"""
        self.update_account(email, status="banned", notes="Permanently banned")
    
    def list_accounts(self) -> list:
        """Tüm hesapları listele"""
        return self.accounts["accounts"]
    
    def get_stats(self) -> dict:
        """Hesap istatistiklerini getir"""
        accounts = self.accounts["accounts"]
        return {
            "total": len(accounts),
            "active": len([a for a in accounts if a["status"] == "active"]),
            "verified": len([a for a in accounts if a["status"] == "verified"]),
            "limited": len([a for a in accounts if a["status"] == "limited"]),
            "banned": len([a for a in accounts if a["status"] == "banned"]),
            "pending": len([a for a in accounts if a["status"] == "pending"]),
        }


# ============ EMAIL HANDLER ============

class DomainEmailHandler:
    """
    Cloudflare Email Routing + Gmail IMAP ile email okuma.
    
    Akış:
    1. Sahibinden → xyz@wazder.dev'e mail atar
    2. Cloudflare catch-all → wwazder@gmail.com'a yönlendirir
    3. Bu class Gmail IMAP ile maili okur
    4. TO header'dan hangi @wazder.dev adresine geldiğini anlar
    """
    
    def __init__(self):
        self.config = DOMAIN_CONFIG
    
    def connect(self):
        """IMAP'a bağlan"""
        mail = imaplib.IMAP4_SSL(
            self.config["imap_server"],
            self.config["imap_port"]
        )
        mail.login(self.config["imap_user"], self.config["imap_password"])
        return mail
    
    def get_verification_code(self, target_email: str, max_wait: int = 120) -> str | None:
        """
        Belirli bir email adresine gelen Sahibinden doğrulama kodunu oku.
        
        Cloudflare catch-all sayesinde tüm @wazder.dev mailleri Gmail'e düşer.
        Bu metod, belirli bir TO adresine gelen maili filtreler.
        
        Args:
            target_email: Hedef email (örn: user123@wazder.dev)
            max_wait: Maksimum bekleme süresi (saniye)
        
        Returns:
            6 haneli doğrulama kodu veya None
        """
        print(f"📧 {target_email} için doğrulama kodu bekleniyor...")
        print(f"   (Cloudflare → Gmail yönlendirmesi kullanılıyor)")
        start = time.time()
        
        while time.time() - start < max_wait:
            try:
                mail = self.connect()
                mail.select("INBOX")
                
                # Son 5 dakikadaki Sahibinden maillerini ara
                # UNSEEN yerine tümünü ara (bazen okunmuş olarak işaretlenebilir)
                date_since = (datetime.now() - timedelta(minutes=5)).strftime("%d-%b-%Y")
                
                # Önce UNSEEN dene
                _, messages = mail.search(None, f'(UNSEEN FROM "sahibinden" SINCE "{date_since}")')
                
                # UNSEEN yoksa tümüne bak
                if not messages[0]:
                    _, messages = mail.search(None, f'(FROM "sahibinden" SINCE "{date_since}")')
                
                if messages[0]:
                    # En yeniden eskiye doğru tara
                    msg_ids = messages[0].split()
                    for msg_id in reversed(msg_ids):
                        _, msg_data = mail.fetch(msg_id, "(RFC822)")
                        
                        for part in msg_data:
                            if isinstance(part, tuple):
                                msg = email.message_from_bytes(part[1])
                                
                                # TO header'ı kontrol et
                                to_header = msg.get("To", "").lower()
                                delivered_to = msg.get("Delivered-To", "").lower()
                                x_forwarded_to = msg.get("X-Forwarded-To", "").lower()
                                
                                # Cloudflare yönlendirmesinde orijinal alıcı bu header'larda olabilir
                                all_recipients = f"{to_header} {delivered_to} {x_forwarded_to}"
                                
                                # Target email bu mailde mi?
                                if target_email.lower() in all_recipients:
                                    # Body'den kodu çıkar
                                    body = self._get_email_body(msg)
                                    code = self._extract_code(body)
                                    
                                    if code:
                                        print(f"   ✅ Kod bulundu: {code}")
                                        # Maili okundu olarak işaretle
                                        mail.store(msg_id, '+FLAGS', '\\Seen')
                                        mail.logout()
                                        return code
                
                mail.logout()
                
            except Exception as e:
                print(f"   ⚠️ IMAP hatası: {e}")
            
            elapsed = int(time.time() - start)
            print(f"   ⏳ Mail bekleniyor... ({elapsed}s / {max_wait}s)")
            time.sleep(5)
        
        print(f"   ❌ {max_wait} saniye içinde kod bulunamadı")
        return None
    
    def _get_email_body(self, msg) -> str:
        """Email body'sini çıkar"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() in ["text/plain", "text/html"]:
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
                    if body:
                        break
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        return body
    
    def _extract_code(self, text: str) -> str | None:
        """Metinden 6 haneli doğrulama kodunu çıkar"""
        matches = re.findall(r'\b(\d{6})\b', text)
        return matches[-1] if matches else None
    
    def test_connection(self) -> bool:
        """Email bağlantısını test et"""
        try:
            mail = self.connect()
            mail.select("INBOX")
            _, messages = mail.search(None, "ALL")
            count = len(messages[0].split()) if messages[0] else 0
            mail.logout()
            print(f"✅ Gmail IMAP bağlantısı başarılı! Inbox'ta {count} mail var.")
            return True
        except Exception as e:
            print(f"❌ Bağlantı hatası: {e}")
            return False


# ============ ACCOUNT CREATOR ============

async def type_like_human(page, text):
    """İnsan gibi tek tek karakter yaz"""
    for char in text:
        if char in '@.':
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
        await asyncio.sleep(random.uniform(0.04, 0.1))


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


async def wait_for_captcha(page, max_wait: int = 120):
    """CAPTCHA varsa kullanıcının geçmesini bekle"""
    
    # İlk kontrol
    url = await page.evaluate("window.location.href")
    text = await page.evaluate("document.body.innerText.substring(0, 500)")
    
    # CAPTCHA var mı?
    has_captcha = 'hloading' in str(url) or \
                  'basılı' in str(text).lower() or \
                  'press' in str(text).lower() or \
                  'hold' in str(text).lower() or \
                  'robot' in str(text).lower()
    
    if not has_captcha:
        return True
    
    print("\n   🤖 CAPTCHA algılandı!")
    print("   👆 Lütfen CAPTCHA'yı geç (butona basılı tut)")
    print("   ⏳ Bekliyorum...\n")
    
    for i in range(max_wait // 2):
        url = await page.evaluate("window.location.href")
        text = await page.evaluate("document.body.innerText.substring(0, 500)")
        
        has_captcha = 'hloading' in str(url) or \
                      'basılı' in str(text).lower() or \
                      'press' in str(text).lower() or \
                      'hold' in str(text).lower()
        
        if not has_captcha:
            print("   ✅ CAPTCHA geçildi!")
            return True
        
        await asyncio.sleep(2)
    
    print("   ❌ CAPTCHA timeout!")
    return False


async def create_sahibinden_account(manager: AccountManager, email_handler: DomainEmailHandler) -> dict | None:
    """
    Yeni bir Sahibinden hesabı oluştur.
    
    Akış:
    1. https://secure.sahibinden.com/kayit sayfasına git
    2. Email gir → İlerle
    3. Şifre gir → Kayıt ol
    4. Email doğrulama kodu gir
    
    Returns:
        Başarılıysa hesap bilgileri, değilse None
    """
    # Yeni hesap bilgileri oluştur
    new_email = manager.generate_email()
    new_password = manager.generate_password()
    
    print("=" * 60)
    print("🆕 YENİ HESAP OLUŞTURULUYOR")
    print("=" * 60)
    print(f"   📧 Email: {new_email}")
    print(f"   🔑 Şifre: {new_password}")
    
    # Hesabı pending olarak ekle
    account = manager.add_account(new_email, new_password, status="pending")
    
    # Browser başlat
    print("\n🚀 Browser başlatılıyor...")
    browser = await uc.start(headless=False)
    
    try:
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
        
        await asyncio.sleep(2)
        
        # Kayıt sayfasına git (doğru URL)
        print("\n📝 Kayıt sayfasına gidiliyor...")
        await page.get("https://secure.sahibinden.com/kayit")
        await asyncio.sleep(3)
        
        # CAPTCHA varsa kullanıcı geçsin
        print("   ⏳ CAPTCHA varsa geçmeni bekliyorum...")
        await wait_for_captcha(page)
        
        # URL kontrolü
        url = await page.evaluate("window.location.href")
        print(f"   📍 URL: {url}")
        
        # ===== ADIM 1: EMAIL GİRİŞİ =====
        print("\n[1/5] Email alanı bulunuyor...")
        
        # Email input'u bul - birkaç selector dene
        email_input = None
        selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[placeholder*="mail"]',
            'input[placeholder*="E-posta"]',
            '#email',
            'input.email-input',
        ]
        
        for selector in selectors:
            try:
                email_input = await page.select(selector)
                if email_input:
                    print(f"   ✅ Email alanı bulundu: {selector}")
                    break
            except:
                pass
        
        if not email_input:
            # JavaScript ile dene
            result = await page.evaluate("""
                (() => {
                    const inputs = document.querySelectorAll('input');
                    for (const inp of inputs) {
                        if (inp.type === 'email' || 
                            inp.name?.includes('mail') || 
                            inp.placeholder?.toLowerCase().includes('mail')) {
                            inp.focus();
                            return 'found';
                        }
                    }
                    // İlk input'u dene
                    if (inputs.length > 0) {
                        inputs[0].focus();
                        return 'first_input';
                    }
                    return 'not_found';
                })()
            """)
            print(f"   JS sonucu: {result}")
            
            if result == 'not_found':
                print("   ❌ Email alanı bulunamadı!")
                manager.update_account(new_email, status="failed", notes="Email field not found")
                return None
        else:
            await email_input.click()
        
        await asyncio.sleep(0.5)
        
        print("\n[2/5] Email yazılıyor...")
        await type_like_human(page, new_email)
        await asyncio.sleep(0.5)
        
        # Email doğrulama
        val = await page.evaluate('document.activeElement?.value || ""')
        print(f"   📝 Girilen: {val}")
        
        # ===== ADIM 2: İLERLE BUTONU =====
        print("\n[3/5] 'İlerle' butonuna tıklanıyor...")
        clicked = False
        
        # Yöntem 1: "İlerle" metnini bul
        try:
            btn = await page.find("İlerle", timeout=3)
            if btn:
                await btn.click()
                clicked = True
                print("   ✅ 'İlerle' butonuna tıklandı")
        except:
            pass
        
        # Yöntem 2: Submit butonu
        if not clicked:
            try:
                btn = await page.select('button[type="submit"]')
                if btn:
                    await btn.click()
                    clicked = True
                    print("   ✅ Submit butonuna tıklandı")
            except:
                pass
        
        # Yöntem 3: JavaScript ile
        if not clicked:
            result = await page.evaluate("""
                (() => {
                    // İlerle butonu ara
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        if (btn.innerText.toLowerCase().includes('ilerle') ||
                            btn.innerText.toLowerCase().includes('devam')) {
                            btn.click();
                            return 'clicked';
                        }
                    }
                    // Submit butonu
                    const submit = document.querySelector('button[type="submit"]');
                    if (submit) {
                        submit.click();
                        return 'submit_clicked';
                    }
                    return 'not_found';
                })()
            """)
            print(f"   JS sonucu: {result}")
            if 'clicked' in result:
                clicked = True
        
        # Yöntem 4: Enter tuşu
        if not clicked:
            await press_key(page, "Enter", "Enter", 13)
            print("   ⏎ Enter tuşuna basıldı")
        
        print("   ⏳ Sayfa yükleniyor...")
        await asyncio.sleep(3)
        await wait_for_captcha(page)
        
        # ===== ADIM 3: ŞİFRE GİRİŞİ =====
        print("\n[4/5] Şifre alanı bulunuyor...")
        
        # Şifre input'u bul
        password_input = None
        pw_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            '#password',
        ]
        
        for selector in pw_selectors:
            try:
                password_input = await page.select(selector)
                if password_input:
                    print(f"   ✅ Şifre alanı bulundu: {selector}")
                    break
            except:
                pass
        
        if password_input:
            await password_input.click()
            await asyncio.sleep(0.3)
            await type_like_human(page, new_password)
            print(f"   ✅ Şifre yazıldı")
            
            # Şifre tekrar varsa
            await asyncio.sleep(0.5)
            password_inputs = await page.select_all('input[type="password"]')
            if len(password_inputs) > 1:
                print("   📝 Şifre tekrar alanı bulundu...")
                await password_inputs[1].click()
                await asyncio.sleep(0.3)
                await type_like_human(page, new_password)
                print(f"   ✅ Şifre tekrar yazıldı")
        else:
            print("   ⚠️ Şifre alanı bulunamadı, TAB ile geçiliyor...")
            await press_key(page, "Tab", "Tab", 9)
            await asyncio.sleep(0.3)
            await type_like_human(page, new_password)
        
        # Kullanım koşullarını kabul et
        print("\n   🔲 Koşullar kabul ediliyor...")
        try:
            checkboxes = await page.select_all('input[type="checkbox"]')
            for cb in checkboxes:
                try:
                    await cb.click()
                    await asyncio.sleep(0.2)
                except:
                    pass
            print("   ✅ Checkbox'lar işaretlendi")
        except:
            pass
        
        # ===== ADIM 4: KAYIT OL BUTONU =====
        print("\n[5/5] 'Kayıt Ol' butonuna tıklanıyor...")
        clicked = False
        
        # Yöntem 1: "Kayıt" metnini bul
        try:
            btn = await page.find("Kayıt", timeout=3)
            if btn:
                await btn.click()
                clicked = True
                print("   ✅ 'Kayıt' butonuna tıklandı")
        except:
            pass
        
        # Yöntem 2: "Üye Ol" metnini bul
        if not clicked:
            try:
                btn = await page.find("Üye Ol", timeout=2)
                if btn:
                    await btn.click()
                    clicked = True
                    print("   ✅ 'Üye Ol' butonuna tıklandı")
            except:
                pass
        
        # Yöntem 3: Submit butonu
        if not clicked:
            try:
                btn = await page.select('button[type="submit"]')
                if btn:
                    await btn.click()
                    clicked = True
                    print("   ✅ Submit butonuna tıklandı")
            except:
                pass
        
        # Yöntem 4: Enter
        if not clicked:
            await press_key(page, "Enter", "Enter", 13)
            print("   ⏎ Enter tuşuna basıldı")
        
        print("\n⏳ Kayıt işleniyor...")
        await asyncio.sleep(5)
        await wait_for_captcha(page)
        
        # ===== EMAIL DOĞRULAMA =====
        url = await page.evaluate("window.location.href")
        text = await page.evaluate("document.body.innerText.substring(0, 1000)")
        
        is_verification = 'dogrulama' in str(url).lower() or \
                         'verification' in str(url).lower() or \
                         'onay' in str(text).lower() or \
                         'doğrulama' in str(text).lower() or \
                         'kod' in str(text).lower()
        
        if is_verification:
            print("\n" + "=" * 50)
            print("📧 EMAIL DOĞRULAMA")
            print("=" * 50)
            
            # Kendi domain'den kodu al
            code = email_handler.get_verification_code(new_email, max_wait=120)
            
            if code:
                print(f"\n🔢 Kod giriliyor: {code}")
                
                # Kod girişi
                result = await page.evaluate(f"""
                    (() => {{
                        const code = "{code}";
                        let inputs = document.querySelectorAll('input[maxlength="1"]');
                        if (inputs.length === 0) {{
                            inputs = document.querySelectorAll('input[type="tel"]');
                        }}
                        
                        const codeInputs = Array.from(inputs).slice(0, 6);
                        
                        for (let i = 0; i < Math.min(code.length, codeInputs.length); i++) {{
                            const inp = codeInputs[i];
                            inp.focus();
                            inp.value = code[i];
                            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                        
                        return codeInputs.map(i => i.value).join('');
                    }})()
                """)
                print(f"   📊 Girilen: {result}")
                
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
                
                # Başarı kontrolü
                url = await page.evaluate("window.location.href")
                if 'dogrulama' not in str(url).lower() and 'verification' not in str(url).lower():
                    print("\n✅ HESAP BAŞARIYLA OLUŞTURULDU!")
                    manager.update_account(new_email, status="verified")
                    
                    # Cookie'leri kaydet
                    cookies_str = await page.evaluate("document.cookie")
                    manager.update_account(new_email, cookies=cookies_str)
                    
                    return manager.accounts["accounts"][-1]
                else:
                    print("\n⚠️ Doğrulama başarısız olabilir")
                    manager.update_account(new_email, status="pending", notes="Verification uncertain")
            else:
                print("\n❌ Doğrulama kodu alınamadı!")
                manager.update_account(new_email, status="pending", notes="Verification code not received")
        else:
            # Doğrulama sayfası yoksa
            print("\n⚠️ Doğrulama sayfası bulunamadı")
            
            # Login kontrolü yap
            text = await page.evaluate("document.body.innerText.substring(0, 500)")
            if 'hoşgeldin' in str(text).lower() or 'hesabım' in str(text).lower():
                print("✅ HESAP BAŞARIYLA OLUŞTURULDU! (Otomatik onay)")
                manager.update_account(new_email, status="verified")
                return manager.accounts["accounts"][-1]
        
        return account
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        manager.update_account(new_email, status="failed", notes=str(e))
        return None
        
    finally:
        print("\n🔒 Browser kapatılıyor...")
        try:
            browser.stop()
        except:
            pass


# ============ MAIN CLI ============

def print_accounts_table(accounts: list):
    """Hesapları tablo formatında yazdır"""
    print("\n" + "=" * 80)
    print(f"{'ID':<4} {'EMAIL':<35} {'STATUS':<12} {'CREATED':<20}")
    print("=" * 80)
    
    for acc in accounts:
        created = acc['created_at'][:19] if acc.get('created_at') else 'N/A'
        status_emoji = {
            'active': '🟢',
            'verified': '✅',
            'pending': '🟡',
            'limited': '🟠',
            'banned': '🔴',
            'failed': '❌'
        }.get(acc['status'], '⚪')
        
        print(f"{acc['id']:<4} {acc['email']:<35} {status_emoji} {acc['status']:<10} {created}")
    
    print("=" * 80)


async def main():
    parser = argparse.ArgumentParser(description='Sahibinden Account Manager')
    parser.add_argument('--create', type=int, help='Oluşturulacak hesap sayısı')
    parser.add_argument('--list', action='store_true', help='Hesapları listele')
    parser.add_argument('--stats', action='store_true', help='İstatistikleri göster')
    parser.add_argument('--rotate', action='store_true', help='Aktif hesabı değiştir')
    parser.add_argument('--set-active', type=str, help='Aktif hesabı ayarla (email)')
    parser.add_argument('--test-email', action='store_true', help='Email yapılandırmasını test et')
    
    args = parser.parse_args()
    
    manager = AccountManager()
    email_handler = DomainEmailHandler()
    
    if args.create:
        print(f"\n🚀 {args.create} yeni hesap oluşturulacak...")
        
        for i in range(args.create):
            print(f"\n{'='*60}")
            print(f"HESAP {i+1}/{args.create}")
            print(f"{'='*60}")
            
            account = await create_sahibinden_account(manager, email_handler)
            
            if account:
                print(f"\n✅ Hesap oluşturuldu: {account['email']}")
            else:
                print(f"\n❌ Hesap oluşturulamadı")
            
            # Hesaplar arası bekleme
            if i < args.create - 1:
                wait_time = random.randint(30, 60)
                print(f"\n⏳ Sonraki hesap için {wait_time} saniye bekleniyor...")
                await asyncio.sleep(wait_time)
    
    elif args.list:
        accounts = manager.list_accounts()
        if accounts:
            print_accounts_table(accounts)
            
            active = manager.get_active_account()
            if active:
                print(f"\n⭐ Aktif hesap: {active['email']}")
        else:
            print("\n📭 Henüz hesap yok. --create ile hesap oluşturun.")
    
    elif args.stats:
        stats = manager.get_stats()
        print("\n📊 HESAP İSTATİSTİKLERİ")
        print("=" * 40)
        print(f"   Toplam:     {stats['total']}")
        print(f"   ✅ Verified: {stats['verified']}")
        print(f"   🟢 Active:   {stats['active']}")
        print(f"   🟡 Pending:  {stats['pending']}")
        print(f"   🟠 Limited:  {stats['limited']}")
        print(f"   🔴 Banned:   {stats['banned']}")
    
    elif args.rotate:
        next_acc = manager.rotate_account()
        if next_acc:
            print(f"\n🔄 Aktif hesap değiştirildi: {next_acc['email']}")
        else:
            print("\n❌ Kullanılabilir hesap bulunamadı!")
    
    elif args.set_active:
        if manager.set_active_account(args.set_active):
            print(f"\n✅ Aktif hesap ayarlandı: {args.set_active}")
        else:
            print(f"\n❌ Hesap bulunamadı: {args.set_active}")
    
    elif args.test_email:
        print("\n📧 Email yapılandırması test ediliyor...")
        print(f"   IMAP Server: {DOMAIN_CONFIG['imap_server']}")
        print(f"   User: {DOMAIN_CONFIG['imap_user']}")
        
        try:
            mail = email_handler.connect()
            mail.select("INBOX")
            _, messages = mail.search(None, "ALL")
            count = len(messages[0].split()) if messages[0] else 0
            print(f"\n   ✅ Bağlantı başarılı! Inbox'ta {count} mail var.")
            mail.logout()
        except Exception as e:
            print(f"\n   ❌ Bağlantı hatası: {e}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
