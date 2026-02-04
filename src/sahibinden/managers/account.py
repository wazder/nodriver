import json
import random
import string
import time
from datetime import datetime
from pathlib import Path
from ..config import ACCOUNTS_FILE, DOMAIN_CONFIG, DEFAULT_PASSWORD_PREFIX

class AccountManager:
    """Manages account persistence and generation."""
    
    def __init__(self):
        self.file_path = ACCOUNTS_FILE
        self.accounts_data = self._load()
        
    def _load(self) -> dict:
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"accounts": []}
        
    def _save(self):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.accounts_data, f, indent=2, ensure_ascii=False)
            
    def generate_email(self) -> str:
        """Generates a random email on the configured domain."""
        # Mix of name-based and random chars for realism
        names = ['can', 'alp', 'cem', 'ada', 'efe', 'ali', 'nill', 'ela']
        prefix = random.choice(names)
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        domain = DOMAIN_CONFIG["domain"]
        return f"{prefix}{suffix}@{domain}"
        
    def generate_password(self) -> str:
        """Generates a strong password."""
        chars = string.ascii_letters + string.digits
        random_part = ''.join(random.choices(chars, k=8))
        return f"{DEFAULT_PASSWORD_PREFIX}{random_part}!"
        
    def create_pending_account(self) -> dict:
        """Creates a new account entry with 'pending' status."""
        email = self.generate_email()
        password = self.generate_password()
        
        account = {
            "id": len(self.accounts_data["accounts"]) + 1,
            "email": email,
            "password": password,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "cookies": None
        }
        
        self.accounts_data["accounts"].append(account)
        self._save()
        return account
        
    def update_status(self, email: str, status: str, cookies: str = None):
        """Updates the status (and cookies) of an account."""
        for acc in self.accounts_data["accounts"]:
            if acc["email"] == email:
                acc["status"] = status
                if cookies:
                    acc["cookies"] = cookies
                acc["last_updated"] = datetime.now().isoformat()
                self._save()
                return
