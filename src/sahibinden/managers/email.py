import imaplib
import email
import time
import re
from datetime import datetime, timedelta
from ..config import DOMAIN_CONFIG

class DomainEmailHandler:
    """
    Handles IMAP connection to retrieve Sahibinden verification codes.
    Uses Cloudflare Email Routing → Gmail pathway.
    """
    
    def __init__(self):
        self.config = DOMAIN_CONFIG
    
    def connect(self):
        """Connects to IMAP server."""
        try:
            mail = imaplib.IMAP4_SSL(
                self.config["imap_server"],
                self.config["imap_port"]
            )
            mail.login(self.config["imap_user"], self.config["imap_password"])
            return mail
        except Exception as e:
            print(f"❌ IMAP Connection Error: {e}")
            raise
    
    def get_verification_code(self, target_email: str, max_wait: int = 120) -> str | None:
        """
        Polls for a verification code sent to 'target_email'.
        """
        print(f"📧 Waiting for code on {target_email}...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                mail = self.connect()
                mail.select("INBOX")
                
                # Search for recent emails from Sahibinden
                date_since = (datetime.now() - timedelta(minutes=5)).strftime("%d-%b-%Y")
                status, messages = mail.search(None, f'(FROM "sahibinden" SINCE "{date_since}")')
                
                if status == "OK" and messages[0]:
                    msg_ids = messages[0].split()
                    # Check newest first
                    for msg_id in reversed(msg_ids):
                        _, msg_data = mail.fetch(msg_id, "(RFC822)")
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                
                                # Verify recipient
                                # Cloudflare routing keeps original TO or adds X-Forwarded-To / Delivered-To
                                headers_to_check = [
                                    msg.get("To", ""),
                                    msg.get("Delivered-To", ""),
                                    msg.get("X-Forwarded-To", "")
                                ]
                                recipient_found = any(target_email.lower() in h.lower() for h in headers_to_check if h)
                                
                                if recipient_found:
                                    body = self._get_email_body(msg)
                                    code = self._extract_code(body)
                                    if code:
                                        print(f"   ✅ Code found: {code}")
                                        try:
                                            mail.store(msg_id, '+FLAGS', '\\Seen')
                                        except:
                                            pass
                                        mail.logout()
                                        return code
                
                mail.logout()
            except Exception as e:
                print(f"   ⚠️ IMAP Check Error: {e}")
            
            time.sleep(5)
            print(f"   ⏳ Waiting... ({int(time.time() - start_time)}s)")

        print("❌ Verification code timeout.")
        return None
    
    def _get_email_body(self, msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            return msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        return ""
    
    def _extract_code(self, text: str) -> str | None:
        # Look for 6 digit code
        matches = re.findall(r'\b(\d{6})\b', text)
        return matches[-1] if matches else None
