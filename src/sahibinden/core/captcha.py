import asyncio
import nodriver as uc

async def solve_press_and_hold(page):
    """
    Detects and solves the 'Press and Hold' CAPTCHA.
    Returns True if solved or not present, False if failed.
    """
    try:
        # 1. Detection
        # Check for common indicators of this captcha
        page_text = await page.evaluate("document.body.innerText")
        is_captcha_present = any(phrase in page_text.lower() for phrase in [
            "press and hold", "basılı tut", "doğrulama", "hloading", "checking connection"
        ])
        
        # Also check for the specific iframe or container often used (Arkose/Datadome/Cloudflare)
        # But 'Sahibinden' usually uses a custom one or Datadome/Cloudflare turnstile.
        # The user mentioned "basılı tutma türü" (Press and hold).
        
        if not is_captcha_present:
            return True # No captcha detected

        print("🤖 CAPTCHA detected. Attempting to solve...")

        # 2. Find the target button/box
        # We need the exact coordinates.
        target_box = await page.evaluate('''
            (() => {
                // Heuristic to find the verify button/box
                const candidates = [
                    '#challenge-stage iframe', 
                    'iframe[src*="cloudflare"]', 
                    '.h-captcha', 
                    'div[class*="verify-button"]',
                    '#challenge-stage div'
                ];
                
                for (let sel of candidates) {
                    let el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) {
                        const rect = el.getBoundingClientRect();
                        return {
                             x: rect.x + rect.width / 2,
                             y: rect.y + rect.height / 2,
                             found: true
                        };
                    }
                }
                
                // Fallback: finding any button that says "Verify" or "Basılı tut"
                // This is risky but often necessary if iframe is hidden
                return null;
            })()
        ''')

        if not target_box or not target_box.get('found'):
            # If we can't find specific element, maybe it's a Shadow DOM issue or simple coordinate click.
            # Some captchas are just "click here".
            pass

        # Since finding the specific "Press Box" can be tricky with dynamic IDs, 
        # let's try a robust coordinate finder if the above missed.
        if not target_box:
             # Try to find the center of the viewport? No, that's bad.
             print("⚠️ Could not locate CAPTCHA button precisely.")
             return False

        x, y = target_box['x'], target_box['y']
        print(f"📍 CAPTCHA Button found at ({x}, {y})")

        # 3. Perform Press and Hold
        # Move mouse
        await page.send(uc.cdp.input_.dispatch_mouse_event(
            type_="mouseMoved", x=x, y=y
        ))
        await asyncio.sleep(0.3)

        # Press
        await page.send(uc.cdp.input_.dispatch_mouse_event(
            type_="mousePressed", x=x, y=y, button="left", click_count=1
        ))
        
        print("🖱️ Holding mouse...")
        
        # Hold for random duration (4-8 seconds usually enough)
        # We should check if the page changes while holding.
        for _ in range(20): # Max 10 seconds
            await asyncio.sleep(0.5)
            # Check if captcha is gone
            remaining_text = await page.evaluate("document.body.innerText")
            if "basılı tut" not in remaining_text.lower() and "hloading" not in remaining_text.lower():
                print("✅ CAPTCHA solved!")
                break
        
        # Release
        await page.send(uc.cdp.input_.dispatch_mouse_event(
            type_="mouseReleased", x=x, y=y, button="left", click_count=1
        ))

        await asyncio.sleep(2) # Wait for navigation/reload
        return True

    except Exception as e:
        print(f"❌ CAPTCHA Error: {e}")
        return False
