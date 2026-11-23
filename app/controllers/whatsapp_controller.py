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

    def remove(self, message_id: str | None) -> None:
        if not message_id:
            return
        with self._lock:
            self._seen.discard(message_id)
            try:
                self._order.remove(message_id)
            except ValueError:
                pass

    def clear(self):
        with self._lock:
            self._seen.clear()
            self._order.clear()


webhook_deduplicator = WebhookDeduplicator()


@whatsapp_bp.post("/webhooks/whatsapp")
def whatsapp_webhook():
    expected_secret = current_app.config.get("WAHA_WEBHOOK_SECRET")
    secret_received = request.headers.get("X-Webhook-Secret") or request.args.get("secret")
    if expected_secret and secret_received != expected_secret:
        return jsonify({"success": False, "error": "Unauthorized webhook"}), 401

    data = request.get_json(silent=True) or {}
    if data.get("event") != "message":
        return jsonify({"status": "ignored", "reason": "unsupported_event"}), 200

    message = data.get("payload") or {}
    if message.get("fromMe"):
        print(f"[WHATSAPP IGNORED] Outgoing message fromMe=True. (Note: Self-messages to your own linked number are ignored).")
        return jsonify({"status": "ignored", "reason": "outgoing_message"}), 200

    message_id = message.get("id")
    if message_id and webhook_deduplicator.is_duplicate(str(message_id)):
        print(f"[WHATSAPP IGNORED] Duplicate message id={message_id}")
        logger.info("Ignoring duplicate WhatsApp message id=%s", message_id)
        return jsonify({"status": "ignored", "reason": "duplicate_message"}), 200

    raw_from = message.get("from")
    if not raw_from or "@g.us" in raw_from:
        return jsonify({"status": "ignored", "reason": "missing_chat_or_group"}), 200

    chat_id = _resolve_whatsapp_chat_id(message)
    print(f"\n[WHATSAPP MESSAGE IN] from='{raw_from}' -> resolved_to='{chat_id}' | Text: '{message.get('body')}'")

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
                print(f"[WHATSAPP MEDIA SAVED] {media_type} saved as ID {record.id}")
                logger.info("Stored WhatsApp %s as media_file_id=%s", media_type, record.id)
            except Exception as media_err:
                print(f"[WHATSAPP MEDIA ERROR] {media_err}")
                logger.warning("Failed to process WhatsApp media: %s", media_err)
                if not user_text:
                    user_text = f"The customer sent a {media_type}, but media processing could not be completed."

        if not user_text:
            return jsonify({"status": "ignored", "reason": "empty_message"}), 200

        result = agent_graph.invoke({"messages": history + [user_text], "customer_id": customer.id})
        response_text = (result.get("response") or "Sorry, I couldn't process your request.").strip()
        ConversationService.add_message(conversation_id, user_text)
        ConversationService.add_message(conversation_id, response_text)

        print(f"[WHATSAPP MESSAGE OUT] Sending reply to {chat_id}: '{response_text[:80]}...'")
        try:
            WahaService.send_text(chat_id, response_text, reply_to=message_id)
            print(f"[WHATSAPP SUCCESS] Reply sent to {chat_id}!")
        except Exception as send_err:
            print(f"[WHATSAPP SEND ERROR] Failed to send WhatsApp response to {chat_id}: {send_err}")
            logger.error("Failed to send WhatsApp response to %s: %s", chat_id, send_err)

        return jsonify({"status": "processed"}), 200
    except Exception:
        if message_id:
            webhook_deduplicator.remove(str(message_id))
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


def _normalize_jid(jid: str | None) -> str | None:
    if not jid or not isinstance(jid, str):
        return None
    jid = jid.strip()
    if jid.endswith("@s.whatsapp.net"):
        return jid.replace("@s.whatsapp.net", "@c.us")
    if jid.endswith("@c.us"):
        return jid
    return None


def _resolve_whatsapp_chat_id(message: dict) -> str:
    """
    Extracts a sendable WhatsApp chat ID (ending with @c.us).
    Resolves modern WhatsApp @lid privacy identifiers by inspecting:
    1. payload._data.key.remoteJid / remoteJidAlt
    2. payload.id ('false_<phone>@s.whatsapp.net_<hash>' or 'false_<phone>@c.us_<hash>')
    3. payload.chatId / author / participant
    4. WAHA Lids API resolution
    5. Fallback to message.get('from')
    """
    # 1. Check direct candidate fields
    candidates = [
        message.get("chatId"),
        message.get("from"),
        message.get("author"),
        message.get("participant"),
    ]
    for candidate in candidates:
        norm = _normalize_jid(candidate)
        if norm:
            return norm

    # 2. Check underlying engine _data (common in NOWEB / Baileys)
    _data = message.get("_data") or {}
    key = _data.get("key") or {}
    data_candidates = [
        key.get("remoteJid"),
        key.get("remoteJidAlt"),
        _data.get("from"),
        _data.get("author"),
        _data.get("chatId"),
    ]
    for candidate in data_candidates:
        norm = _normalize_jid(candidate)
        if norm:
            return norm

    # 3. Check message.id (e.g. 'false_201012345678@s.whatsapp.net_3EB0...')
    mid = str(message.get("id") or "")
    if "_" in mid:
        parts = mid.split("_")
        for part in parts:
            norm = _normalize_jid(part)
            if norm:
                return norm

    # 4. If from is @lid, resolve via WAHA Lids API
    from_jid = str(message.get("from") or message.get("chatId") or "").strip()
    if "@lid" in from_jid:
        resolved = WahaService.resolve_lid(from_jid)
        if resolved:
            logger.info("Successfully resolved LID %s to %s via WAHA Lids API", from_jid, resolved)
            return resolved

    # 5. Return whatever we have as fallback
    return from_jid


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
