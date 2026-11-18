import requests
from app.config import Config


class WahaService:
    @staticmethod
    def _headers():
        if not Config.WAHA_BASE_URL or not Config.WAHA_API_KEY:
            raise RuntimeError("WAHA_BASE_URL and WAHA_API_KEY must be configured")
        return {"X-Api-Key": Config.WAHA_API_KEY}

    @staticmethod
    def send_text(chat_id: str, text: str):
        url = f"{Config.WAHA_BASE_URL.rstrip('/')}/api/sendText"
        response = requests.post(url, json={"session": Config.WAHA_SESSION, "chatId": chat_id, "text": text}, headers={**WahaService._headers(), "Content-Type": "application/json"}, timeout=20)
        response.raise_for_status()
        return response.json() if response.content else {"success": True}

    @staticmethod
    def download_media(message: dict):
        """Download media exposed by WAHA webhook payloads. Supports media.url and message-id endpoint."""
        media = message.get("media") or {}
        url = media.get("url") or message.get("mediaUrl")
        headers = WahaService._headers()
        if url:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            return response.content, media.get("mimetype") or media.get("mimeType") or response.headers.get("Content-Type", "").split(";")[0], media.get("filename") or media.get("fileName")

        message_id = message.get("id")
        if message_id:
            url = f"{Config.WAHA_BASE_URL.rstrip('/')}/api/{Config.WAHA_SESSION}/messages/{message_id}/media"
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            return response.content, response.headers.get("Content-Type", "").split(";")[0], None
        raise ValueError("WAHA webhook did not include a downloadable media URL or message id.")
