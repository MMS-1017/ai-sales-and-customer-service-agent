import collections
import logging
from pathlib import Path
import threading

from flask import Blueprint, current_app, jsonify, request

from app.agent import agent_graph
from app.extensions import db
from app.models import Customer
from app.services.conversation_service import ConversationService
from app.services.media_service import MediaService
from app.services.waha_service import WahaService

logger = logging.getLogger(__name__)
whatsapp_bp = Blueprint("whatsapp", __name__)


class WebhookDeduplicator:
    """Thread-safe bounded in-memory cache to detect and ignore duplicate webhook deliveries."""

    def __init__(self, maxsize: int = 2000):
        self._maxsize = maxsize
        self._seen = set()
        self._order = collections.deque()
        self._lock = threading.Lock()

    def is_duplicate(self, message_id: str | None) -> bool:
        if not message_id:
            return False
        with self._lock:
            if message_id in self._seen:
                return True
            self._seen.add(message_id)
            self._order.append(message_id)
            if len(self._order) > self._maxsize:
                oldest = self._order.popleft()
                self._seen.discard(oldest)
            return False

    def clear(self):
        with self._lock:
            self._seen.clear()
            self._order.clear()


webhook_deduplicator = WebhookDeduplicator()


@whatsapp_bp.post("/webhooks/whatsapp")
def whatsapp_webhook():
    expected_secret = current_app.config.get("WAHA_WEBHOOK_SECRET")
    if expected_secret and request.headers.get("X-Webhook-Secret") != expected_secret:
        return jsonify({"success": False, "error": "Unauthorized webhook"}), 401

    data = request.get_json(silent=True) or {}
    if data.get("event") != "message":
        return jsonify({"status": "ignored", "reason": "unsupported_event"}), 200

    message = data.get("payload") or {}
    if message.get("fromMe"):
        return jsonify({"status": "ignored", "reason": "outgoing_message"}), 200

    message_id = message.get("id")
    if message_id and webhook_deduplicator.is_duplicate(str(message_id)):
        logger.info("Ignoring duplicate WhatsApp message id=%s", message_id)
        return jsonify({"status": "ignored", "reason": "duplicate_message"}), 200

    chat_id = message.get("from")
    if not chat_id or "@g.us" in chat_id:
        return jsonify({"status": "ignored", "reason": "missing_chat_or_group"}), 200

    try:
        customer = get_or_create_whatsapp_customer(chat_id)
        conversation_id = f"whatsapp:{chat_id}"
        history = ConversationService.get_history(conversation_id)
        user_text = (message.get("body") or "").strip()
        media_type = _detect_media_type(message)

        if media_type:
            try:
                content, mime_type, supplied_name = WahaService.download_media(message)
                file_name = supplied_name or _fallback_filename(message, media_type, mime_type)
                record, extracted_text = MediaService.save_and_process(
                    file_name=file_name, content=content, mime_type=mime_type,
                    media_type=media_type, customer_id=customer.id, source="whatsapp",
                )
                prefix = "Image analysis" if media_type == "image" else "Audio transcription"
                user_text = "\n".join(part for part in [user_text, f"[{prefix}: {extracted_text}]" if extracted_text else ""] if part)
                if not user_text:
                    user_text = f"The customer sent a {media_type}."
                logger.info("Stored WhatsApp %s as media_file_id=%s", media_type, record.id)
            except Exception as media_err:
                logger.warning("Failed to process WhatsApp media: %s", media_err)
                if not user_text:
                    user_text = f"The customer sent a {media_type}, but media processing could not be completed."

        if not user_text:
            return jsonify({"status": "ignored", "reason": "empty_message"}), 200

        result = agent_graph.invoke({"messages": history + [user_text], "customer_id": customer.id})
        response_text = (result.get("response") or "Sorry, I couldn't process your request.").strip()
        ConversationService.add_message(conversation_id, user_text)
        ConversationService.add_message(conversation_id, response_text)

        try:
            WahaService.send_text(chat_id, response_text)
        except Exception as send_err:
            logger.error("Failed to send WhatsApp response to %s: %s", chat_id, send_err)

        return jsonify({"status": "processed"}), 200
    except Exception:
        db.session.rollback()
        logger.exception("Failed to process WAHA message from %s", chat_id)
        return jsonify({"success": False, "error": "Message processing failed"}), 500


def _detect_media_type(message):
    message_type = (message.get("type") or "").lower()
    media = message.get("media") or {}
    mime = (media.get("mimetype") or media.get("mimeType") or "").lower()
    if message_type in {"image", "image_message"} or mime.startswith("image/"):
        return "image"
    if message_type in {"audio", "ptt", "voice", "audio_message"} or mime.startswith("audio/"):
        return "audio"
    return None


def _fallback_filename(message, media_type, mime_type):
    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/webm": "webm"}.get(mime_type, "bin")
    message_id = str(message.get("id") or "upload").replace("/", "_")
    return f"{media_type}_{message_id}.{extension}"


def get_or_create_whatsapp_customer(chat_id: str) -> Customer:
    normalized = chat_id.split("@", 1)[0].replace("+", "")
    email = f"whatsapp_{normalized}@whatsapp.local"
    customer = Customer.query.filter_by(email=email).first()
    if customer:
        return customer
    try:
        customer = Customer(name=f"WhatsApp Customer {normalized}", email=email)
        db.session.add(customer)
        db.session.commit()
        return customer
    except Exception:
        db.session.rollback()
        customer = Customer.query.filter_by(email=email).first()
        if customer:
            return customer
        raise
