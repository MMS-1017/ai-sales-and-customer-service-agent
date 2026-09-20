import hashlib
import hmac

import requests

from app.config import Config


class FacebookService:

    @staticmethod
    def verify_signature(raw_body, signature):
        if not Config.FACEBOOK_APP_SECRET:
            return True

        if not signature:
            return False

        if not signature.startswith("sha256="):
            return False

        expected = hmac.new(
            Config.FACEBOOK_APP_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        received = signature.split("=", 1)[1]

        return hmac.compare_digest(expected, received)

    @staticmethod
    def send_message(recipient_id, message):
        if not Config.FACEBOOK_PAGE_ACCESS_TOKEN:
            raise RuntimeError(
                "FACEBOOK_PAGE_ACCESS_TOKEN is not configured."
            )

        if not Config.FACEBOOK_PAGE_ID:
            raise RuntimeError(
                "FACEBOOK_PAGE_ID is not configured."
            )

        url = (
            f"https://graph.facebook.com/"
            f"{Config.FACEBOOK_GRAPH_VERSION}/"
            f"{Config.FACEBOOK_PAGE_ID}/messages"
        )

        payload = {
            "recipient": {
                "id": recipient_id,
            },
            "messaging_type": "RESPONSE",
            "message": {
                "text": message,
            },
        }

        response = requests.post(
            url,
            params={
                "access_token": Config.FACEBOOK_PAGE_ACCESS_TOKEN,
            },
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

        return response.json()