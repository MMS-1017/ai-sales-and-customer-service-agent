import hashlib
import hmac
import logging

from flask import current_app, has_app_context
import requests

from app.config import Config

logger = logging.getLogger(__name__)


class FacebookService:

    @staticmethod
    def verify_signature(raw_body, signature, *, allow_unconfigured: bool = True):
        secret = Config.FACEBOOK_APP_SECRET
        if not secret and has_app_context():
            secret = current_app.config.get("FACEBOOK_APP_SECRET")

        if not secret:
            if allow_unconfigured:
                logger.warning("FACEBOOK_APP_SECRET is not configured; webhook signature check skipped.")
                return True
            logger.error("FACEBOOK_APP_SECRET is missing and REQUIRE_WEBHOOK_SECRETS is enabled.")
            return False

        if not signature or not signature.startswith("sha256="):
            return False

        expected = hmac.new(
            secret.encode("utf-8"),
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