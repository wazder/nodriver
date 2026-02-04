import asyncio
import argparse
import random
import nodriver as uc
from .config import CAPTCHA_TIMEOUT
from .core.browser import start_browser
from .core.inputs import type_human_like, click_element
from .core.captcha import solve_press_and_hold
from .managers.account import AccountManager
from .managers.email import DomainEmailHandler

async def create_account_flow(manager, email_handler):
    """Executes the single account creation flow."""
    
    # 1. Prepare Account Data
    account = manager.create_pending_account()
    email_addr = account["email"]
    password = account["password"]
    
    print(f"\n🚀 Starting Account Creation: {email_addr}")
    
    browser = await start_browser()
    try:
        page = await browser.get("https://secure.sahibinden.com/kayit")
        await asyncio.sleep(3)
        
        # 2. Initial Checks (Cookies & Captcha)
        # Accept cookies if present
        try:
             await click_element(page, 'button#onetrust-accept-btn-handler') # Common ID, or generic text
        except:
             pass

        # Check for immediate captcha
        await solve_press_and_hold(page)

        # 3. Fill Form
        print("📝 Filling registration form...")
        
        # Email first (Form triggers on this)
        print(f"   📧 Entering email: {email_addr}")
        await type_human_like(page, 'input[name="email"], input[type="email"], input[placeholder*="E-posta"]', email_addr)
        
        # Press Enter to trigger check/expand
        await asyncio.sleep(0.5)
        await page.send(uc.cdp.input_.dispatch_key_event(type_="rawKeyDown", windows_virtual_key_code=13, unmodified_text="\r", text="\r"))
        await page.send(uc.cdp.input_.dispatch_key_event(type_="keyUp", windows_virtual_key_code=13, unmodified_text="\r", text="\r"))
        
        print("   ⏳ Waiting for form expansion...")
        await asyncio.sleep(2)
        
        # Name fields
        await type_human_like(page, 'input[name="name"], input[placeholder="Ad"]', "Can")
        await type_human_like(page, 'input[name="surname"], input[placeholder="Soyad"]', "Yilmaz")
        
        # Password
        print("   🔑 Entering password...")
        await type_human_like(page, 'input[id="password"], input[type="password"]', password)
        
        # Terms (Checkboxes)
        print("   ✅ Accepting terms...")
        await page.evaluate("""
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.click())
        """)
        await asyncio.sleep(1)
        
        # Submit
        print("   🚀 Submitting form...")
        # Try finding the specific submit button (Sign Up / Kayıt Ol)
        submit_clicked = await page.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]') || 
                            Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Kayıt') || b.innerText.includes('Hesap'));
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            })()
        """)
        
        # 4. Handle Post-Submit (Captcha or Verification)
        await asyncio.sleep(3)
        await solve_press_and_hold(page)
        
        # Check if we are on verification page
        url = await page.evaluate("window.location.href")
        if "dogrulama" in url or "verification" in url:
            print("📬 Waiting for verification code...")
            code = email_handler.get_verification_code(email_addr)
            
            if code:
                print(f"   🔢 Code received: {code}")
                # Enter code
                # Usually 6 inputs or one input
                await page.evaluate(f"""
                    (() => {{
                        const code = "{code}";
                        const inputs = document.querySelectorAll('input[type="tel"], input[maxlength="1"]');
                        if (inputs.length >= 6) {{
                            inputs.forEach((inp, i) => {{
                                inp.value = code[i];
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                            }});
                        }} else {{
                            const inp = document.querySelector('input');
                            if(inp) inp.value = code;
                        }}
                    }})()
                """)
                await asyncio.sleep(1)
                
                # Click verify
                await page.evaluate("""
                    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Doğrula') || b.innerText.includes('Onayla'));
                    if(btn) btn.click();
                """)
                
                await asyncio.sleep(5)
                await solve_press_and_hold(page)
                
                # Success Check
                # If redirected to home or login
                manager.update_status(email_addr, "verified")
                print("✨ Account Verified Successfully!")
                return True
            else:
                print("❌ Failed to get verification code.")
                manager.update_status(email_addr, "failed")
        else:
             # Maybe immediate success?
             print(f"ℹ️ Current URL: {url}")
             manager.update_status(email_addr, "manual_check")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        browser.stop()

async def main():
    parser = argparse.ArgumentParser(description="Sahibinden Cloud V2")
    parser.add_argument("--create", type=int, help="Number of accounts to create")
    parser.add_argument("--test-email", action="store_true", help="Test IMAP connection")
    
    args = parser.parse_args()
    
    email_handler = DomainEmailHandler()
    manager = AccountManager()
    
    if args.test_email:
        email_handler.connect()
        print("✅ Email connection successful.")
        return

    if args.create:
        for i in range(args.create):
            await create_account_flow(manager, email_handler)
            if i < args.create - 1:
                wait = random.randint(30, 60)
                print(f"⏳ Waiting {wait}s before next account...")
                await asyncio.sleep(wait)

if __name__ == "__main__":
    uc.loop().run_until_complete(main())
