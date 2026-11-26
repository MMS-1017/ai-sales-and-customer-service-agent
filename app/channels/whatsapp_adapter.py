from __future__ import annotations

import hmac
import logging
import mimetypes
from typing import Any

from flask import Request, current_app
from pydantic import BaseModel, ConfigDict, Field
import requests

from app.channels.base import (
    ChannelAdapter,
    ChannelAuthError,
    ChannelDeliveryError,
    ChannelDeliveryResult,
    ChannelValidationError,
    DownloadedMedia,
    split_text_chunks,
)
from app.schemas import (
    ChannelType,
    MediaType,
    UnifiedAgentResponse,
    UnifiedAttachment,
    UnifiedIncomingMessage,
    UnifiedOutboundMessage,
)
from app.services.waha_service import WahaService

logger = logging.getLogger(__name__)


class WhatsAppMediaPayload(BaseModel):
    """Raw WAHA media metadata block."""

    url: str | None = None
    mimetype: str | None = None
    mimeType: str | None = None
    filename: str | None = None
    fileName: str | None = None

    model_config = ConfigDict(extra="allow")


class WhatsAppMessagePayload(BaseModel):
    """Validated raw inbound payload from a WAHA WhatsApp webhook event."""

    id: str | None = None
    from_: str | None = Field(default=None, alias="from")
    fromMe: bool = False
    body: str | None = ""
    type: str | None = ""
    chatId: str | None = None
    timestamp: int | float | str | None = None
    media: WhatsAppMediaPayload | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


def normalize_whatsapp_jid(jid: str | None) -> str | None:
    """Normalize @s.whatsapp.net and @c.us JIDs into canonical @c.us format."""
    if not jid or not isinstance(jid, str):
        return None
    cleaned = jid.strip()
    if cleaned.endswith("@s.whatsapp.net"):
        return cleaned.replace("@s.whatsapp.net", "@c.us")
    if cleaned.endswith("@c.us"):
        return cleaned
    return None


def resolve_whatsapp_chat_id(message: dict[str, Any]) -> str:
    """Extract a sendable WhatsApp chat ID (resolving @lid identifiers if needed)."""
    candidates = [
        message.get("chatId"),
        message.get("from"),
        message.get("author"),
        message.get("participant"),
    ]
    for candidate in candidates:
        norm = normalize_whatsapp_jid(candidate)
        if norm:
            return norm

    _data = message.get("_data") or {}
    key = _data.get("key") or {}
    for candidate in [
        key.get("remoteJid"),
        key.get("remoteJidAlt"),
        _data.get("from"),
        _data.get("author"),
        _data.get("chatId"),
    ]:
        norm = normalize_whatsapp_jid(candidate)
        if norm:
            return norm

    mid = str(message.get("id") or "")
    if "_" in mid:
        for part in mid.split("_"):
            norm = normalize_whatsapp_jid(part)
            if norm:
                return norm

    from_jid = str(message.get("from") or message.get("chatId") or "").strip()
    if "@lid" in from_jid:
        resolved = WahaService.resolve_lid(from_jid)
        if resolved:
            logger.info("Resolved LID %s to %s via WAHA Lids API", from_jid, resolved)
            return resolved

    return from_jid


def _detect_wa_media_type(parsed: WhatsAppMessagePayload) -> MediaType | None:
    msg_type = (parsed.type or "").lower()
    mime = ""
    if parsed.media:
        mime = (parsed.media.mimetype or parsed.media.mimeType or "").lower()

    if msg_type in {"image", "image_message"} or mime.startswith("image/"):
        return MediaType.IMAGE
    if (
        msg_type in {"audio", "ptt", "voice", "audio_message"}
        or mime.startswith("audio/")
        or mime in {"video/mp4", "video/3gpp", "video/quicktime"}
    ):
        return MediaType.AUDIO
    return None


def _fallback_filename(message_id: str | None, media_type: MediaType, mime_type: str) -> str:
    ext_map = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "audio/ogg": "ogg",
        "audio/mpeg": "mp3",
        "audio/mp4": "m4a",
        "audio/webm": "webm",
    }
    ext = ext_map.get(mime_type) or (mimetypes.guess_extension(mime_type) or ".bin").lstrip(".")
    safe_id = str(message_id or "upload").replace("/", "_")
    return f"{media_type.value}_{safe_id}.{ext}"


class WhatsAppAdapter(ChannelAdapter):
    """Channel adapter for WhatsApp via WAHA."""

    channel_name = ChannelType.WHATSAPP.value
    max_text_length = 4096
    supports_attachments = True
    delivers_asynchronously = True
    strict_media_validation = False

    def verify_webhook(self, req: Request) -> None:
        expected_secret = current_app.config.get("WAHA_WEBHOOK_SECRET") or ""
        secret_received = req.headers.get("X-Webhook-Secret") or req.args.get("secret") or ""

        if expected_secret:
            if not hmac.compare_digest(str(secret_received), str(expected_secret)):
                raise ChannelAuthError("Unauthorized webhook", status_code=401)
            return

        require_secret = current_app.config.get("REQUIRE_WEBHOOK_SECRETS", False)
        if require_secret and not current_app.config.get("TESTING"):
            raise ChannelAuthError("WAHA_WEBHOOK_SECRET is required", status_code=401)

    def parse_payload_dict(self, data: dict[str, Any]) -> tuple[list[UnifiedIncomingMessage], str | None]:
        """Normalize a parsed WAHA webhook JSON dict without requiring a Flask Request."""
        if data.get("event") != "message":
            return [], "unsupported_event"

        raw_payload = data.get("payload") or {}
        if not isinstance(raw_payload, dict):
            raise ChannelValidationError("Invalid WhatsApp payload object.")

        parsed = WhatsAppMessagePayload.model_validate(raw_payload)
        if parsed.fromMe:
            return [], "outgoing_message"

        raw_from = parsed.from_
        if not raw_from or "@g.us" in raw_from:
            return [], "missing_chat_or_group"

        chat_id = resolve_whatsapp_chat_id(raw_payload)
        session_id = str(data.get("session") or "").strip()

        attachments: list[UnifiedAttachment] = []
        media_type = _detect_wa_media_type(parsed)
        if media_type:
            mime = None
            file_name = None
            media_url = None
            if parsed.media:
                raw_mime = parsed.media.mimetype or parsed.media.mimeType or ""
                mime = raw_mime.split(";", 1)[0].strip().lower() or None
                file_name = parsed.media.filename or parsed.media.fileName
                media_url = parsed.media.url

            attachments.append(
                UnifiedAttachment(
                    media_type=media_type,
                    file_name=file_name,
                    mime_type=mime,
                    url=media_url,
                    metadata={"waha_payload": dict(raw_payload)},
                )
            )

        incoming = UnifiedIncomingMessage(
            external_message_id=str(parsed.id) if parsed.id is not None else None,
            channel=self.channel_name,
            channel_account_id=session_id,
            external_user_id=chat_id,
            conversation_id=f"{self.channel_name}:{chat_id}",
            text=parsed.body or "",
            attachments=attachments,
            timestamp=parsed.timestamp,
            metadata={"raw_from": raw_from, "session": session_id},
        )

        if not incoming.has_content:
            return [], "empty_message"

        return [incoming], None

    def parse_incoming(self, req: Request) -> tuple[list[UnifiedIncomingMessage], str | None]:
        data = req.get_json(silent=True) or {}
        return self.parse_payload_dict(data)

    def download_attachment(
        self,
        attachment: UnifiedAttachment,
        message: UnifiedIncomingMessage,
    ) -> DownloadedMedia:
        waha_payload = attachment.metadata.get("waha_payload") or {
            "id": message.external_message_id,
            "media": {"url": attachment.url, "mimetype": attachment.mime_type, "filename": attachment.file_name},
        }
        content, mime_type, supplied_name = WahaService.download_media(waha_payload)
        clean_mime = (mime_type or attachment.mime_type or "").split(";", 1)[0].strip().lower()
        file_name = supplied_name or attachment.file_name or _fallback_filename(
            message.external_message_id, attachment.media_type, clean_mime
        )
        return DownloadedMedia(content=content, mime_type=clean_mime, file_name=file_name)

    def send_message(self, outbound: UnifiedOutboundMessage) -> ChannelDeliveryResult:
        text_to_send = (outbound.text or "").strip()
        if not text_to_send and outbound.attachments:
            urls = [att.url for att in outbound.attachments if att.url]
            text_to_send = "\n".join(urls) if urls else "[Media attachment]"

        chunks = split_text_chunks(text_to_send, self.max_text_length)
        if not chunks:
            return ChannelDeliveryResult(success=True, chunks_sent=0, delivery_status="skipped")

        last_provider_response: dict[str, Any] = {}
        try:
            for idx, chunk in enumerate(chunks):
                reply_to = outbound.reply_to_external_message_id if idx == 0 else None
                res = WahaService.send_text(outbound.recipient_id, chunk, reply_to=reply_to)
                if isinstance(res, dict):
                    last_provider_response = res
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            retryable = status is None or status >= 500 or status == 429
            raise ChannelDeliveryError(
                f"WAHA send failed (status={status}): {exc}",
                retryable=retryable,
                status_code=status,
            ) from exc
        except requests.RequestException as exc:
            raise ChannelDeliveryError(f"WAHA network error: {exc}", retryable=True) from exc
        except Exception as exc:
            raise ChannelDeliveryError(f"WAHA unexpected error: {exc}", retryable=False) from exc

        ext_id = last_provider_response.get("id") or last_provider_response.get("key", {}).get("id")
        return ChannelDeliveryResult(
            success=True,
            external_message_id=str(ext_id) if ext_id else None,
            chunks_sent=len(chunks),
            delivery_status="sent",
            metadata={"provider_response": last_provider_response},
        )
