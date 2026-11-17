import requests
from app.config import Config

class WahaService:
    
    @staticmethod
    def send_text(chat_id: str, text: str):

        if not Config.WAHA_BASE_URL:
            raise RuntimeError("WAHA_BASE_URL is not configured")
        
        if not Config.WAHA_API_KEY:
            raise RuntimeError("WAHA_API_KEY is not configured")

        url = f"{Config.WAHA_BASE_URL.rstrip('/')}/api/sendText"
        
        headers = {
            "X-Api-Key": Config.WAHA_API_KEY,
            "Content-Type": "application/json",
        }
        
        payload = {
            "session": Config.WAHA_SESSION,
            "chatId": chat_id,
            "text": text,
        }

        response = requests.post(url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json() if response.content else {"success": True}