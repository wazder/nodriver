import asyncio
import random
import nodriver as uc

async def type_human_like(page, selector: str, text: str):
    """
    Types text into an element specified by selector in a human-like manner using CDP.
    Ensures the element is focused and triggers all necessary keyboard events.
    """
    try:
        # 1. Find the element
        element = await page.select(selector, timeout=5)
        if not element:
            print(f"⚠️ Element not found for typing: {selector}")
            return False

        # 2. Focus the element (Click + JS Focus)
        await element.click()
        await asyncio.sleep(0.2)
        await page.evaluate(f"""
            const el = document.querySelector('{selector}');
            if(el) el.focus();
        """)
        
        # 3. Clear existing content (Select All + Backspace)
        # Check if empty first to save time? No, safer to just clear.
        # Command/Control + A
        await page.send(uc.cdp.input_.dispatch_key_event(type_="keyDown", modifiers=2, text="a")) # 2 = Ctrl/Cmd
        await page.send(uc.cdp.input_.dispatch_key_event(type_="keyUp", modifiers=2, text="a"))
        await asyncio.sleep(0.05)
        # Backspace
        await page.send(uc.cdp.input_.dispatch_key_event(type_="keyDown", text="\u0008")) # Backspace char
        await page.send(uc.cdp.input_.dispatch_key_event(type_="keyUp", text="\u0008"))
        await asyncio.sleep(0.1)

        # 4. Type characters
        for char in text:
            # KeyDown
            await page.send(uc.cdp.input_.dispatch_key_event(type_="keyDown", text=char))
            
            # Char (only for printable)
            await page.send(uc.cdp.input_.dispatch_key_event(type_="char", text=char))
            
            # KeyUp
            await page.send(uc.cdp.input_.dispatch_key_event(type_="keyUp", text=char))
            
            # Random delay between 50ms and 150ms
            await asyncio.sleep(random.uniform(0.05, 0.15))

        # 5. Verification
        value = await page.evaluate(f"document.querySelector('{selector}').value")
        if value != text:
            print(f"⚠️ Typing mismatch. Expected '{text}', got '{value}'. Retrying via JS force...")
            # Fallback: Force value via JS if typing failed (e.g. some complex React state blocking)
            await page.evaluate(f'''
                (() => {{
                    const el = document.querySelector('{selector}');
                    if(el) {{
                        el.value = "{text}";
                        el.dispatchEvent(new Event('input', {{bubbles: true}}));
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }}
                }})()
            ''')
        
        return True

    except Exception as e:
        print(f"❌ Error typing into {selector}: {e}")
        return False

async def click_element(page, selector: str):
    """
    Reliably clicks an element.
    """
    try:
        element = await page.select(selector, timeout=5)
        if element:
            await element.click()
            return True
        return False
    except Exception as e:
        print(f"❌ Error clicking {selector}: {e}")
        return False
