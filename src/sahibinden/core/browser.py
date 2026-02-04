import nodriver as uc
from ..config import HEADLESS

async def start_browser():
    """Starts the browser with optimal settings for automation."""
    # Nodriver by default provides good stealth.
    # We can add specific flags if needed, but defaults are usually best.
    browser = await uc.start(
        headless=HEADLESS,
        # Mac often needs this for stability
        browser_args=[
            "--no-first-run",
            "--password-store=basic",
            "--lang=tr-TR,tr" # Important for Turkish site
        ]
    )
    return browser
