import logging
import requests
from app.config import Config

logger = logging.getLogger(__name__)


class WahaService:
    @staticmethod
    def _headers():
        if not Config.WAHA_BASE_URL or not Config.WAHA_API_KEY:
            raise RuntimeError("WAHA_BASE_URL and WAHA_API_KEY must be configured")
        return {"X-Api-Key": Config.WAHA_API_KEY}

    @staticmethod
    def resolve_lid(lid: str) -> str | None:
        """
        Resolves a WhatsApp '@lid' privacy identifier to a standard '@c.us' phone JID via WAHA Lids API.
        """
        if not lid:
            return None
        clean_lid = lid.strip()
        headers = WahaService._headers()
        session = Config.WAHA_SESSION or "default"
        base_url = Config.WAHA_BASE_URL.rstrip("/")

        # Try querying with full JID and without @lid
        variants = [clean_lid, clean_lid.split("@")[0]]
        for variant in variants:
            url = f"{base_url}/api/{session}/lids/{variant}"
            try:
                res = requests.get(url, headers=headers, timeout=6)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, dict):
                        resolved = data.get("chatId") or data.get("pn") or data.get("phoneNumber") or data.get("id")
                    elif isinstance(data, str):
                        resolved = data
                    else:
                        resolved = None

                    if resolved and isinstance(resolved, str):
                        resolved = resolved.strip()
                        if resolved.endswith("@s.whatsapp.net"):
                            return resolved.replace("@s.whatsapp.net", "@c.us")
                        if resolved.endswith("@c.us"):
                            return resolved
                        if "@" not in resolved:
                            return f"{resolved}@c.us"
            except Exception as err:
                logger.debug("WAHA Lids API resolution attempt failed for %s: %s", variant, err)

        return None

    @staticmethod
    def send_text(chat_id: str, text: str, reply_to: str | None = None):
        # Normalize @s.whatsapp.net to @c.us
        if chat_id.endswith("@s.whatsapp.net"):
            chat_id = chat_id.replace("@s.whatsapp.net", "@c.us")
        elif chat_id.endswith("@lid"):
            # Attempt resolution if LID was passed
            resolved = WahaService.resolve_lid(chat_id)
            if resolved:
                chat_id = resolved

        url = f"{Config.WAHA_BASE_URL.rstrip('/')}/api/sendText"
        payload = {"session": Config.WAHA_SESSION, "chatId": chat_id, "text": text}
        if reply_to:
            payload["reply_to"] = str(reply_to)

        headers = {**WahaService._headers(), "Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=20)

        # If sending with reply_to failed with 422, retry without reply_to (some engines reject reply_to)
        if response.status_code == 422 and reply_to:
            print(f"[WAHA 422] Retrying without reply_to for {chat_id}... (WAHA response: {response.text})")
            payload.pop("reply_to", None)
            response = requests.post(url, json=payload, headers=headers, timeout=20)

        if response.status_code != 200:
            print(f"[WAHA SEND ERROR] Status: {response.status_code}, Body: {response.text}")
            logger.error("WAHA sendText error (%s) for %s: %s", response.status_code, chat_id, response.text)

        response.raise_for_status()
        return response.json() if response.content else {"success": True}

    @staticmethod
    def get_session_info():
        """Fetches status of all sessions from WAHA for diagnostics."""
        url = f"{Config.WAHA_BASE_URL.rstrip('/')}/api/sessions"
        try:
            res = requests.get(url, headers=WahaService._headers(), timeout=5)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            return [{"error": str(e)}]
        return []

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
