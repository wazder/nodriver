import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
ACCOUNTS_FILE = BASE_DIR / "sahibinden_accounts.json"

# Domain Configuration
# In a real app, these should probably be env vars, but we'll keep them here for now as requested
DOMAIN_CONFIG = {
    "domain": "wazder.com",
    "imap_server": "imap.gmail.com",
    "imap_port": 993,
    "imap_user": "wwazder@gmail.com",
    # Retrieve password from env var if possible, else hardcode (user provided hardcoded)
    "imap_password": os.getenv("IMAP_PASSWORD", "rxlkdfxwbhlanqhy"),
}

# Automation Settings
DEFAULT_PASSWORD_PREFIX = "SahPass"
BROWSER_TIMEOUT = 30
CAPTCHA_TIMEOUT = 120
HEADLESS = False  # Set to True for production if stealth allows
