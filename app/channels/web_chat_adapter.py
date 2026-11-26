from __future__ import annotations

import mimetypes
from typing import Any

from flask import Request
from pydantic import BaseModel, ConfigDict, field_validator
from werkzeug.utils import secure_filename

from app.channels.base import (
    ChannelAdapter,
    ChannelDeliveryResult,
    ChannelValidationError,
    DownloadedMedia,
)
from app.schemas import (
    ChannelType,
    MediaType,
    UnifiedAgentResponse,
    UnifiedAttachment,
    UnifiedIncomingMessage,
    UnifiedOutboundMessage,
)

_AUDIO_MIME_TYPES = {"video/mp4", "video/3gpp", "video/quicktime"}
_AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".mp4", ".aac")


class WebChatPayload(BaseModel):
    """Validated inbound payload from the Website Chat API."""

    message: str = ""
    customer_id: int | None = None
    visitor_id: str | None = None
    conversation_id: str = "default"
    channel_account_id: str = "web_store"

    model_config = ConfigDict(extra="allow")

    @field_validator("message", mode="before")
    @classmethod
    def _clean_message(cls, value: Any) -> str:
        return ("" if value is None else str(value)).strip()

    @field_validator("customer_id", mode="before")
    @classmethod
    def _parse_customer_id(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError("Invalid customer ID.")
        try:
            return int(value)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid customer ID.") from exc

    @field_validator("visitor_id", mode="before")
    @classmethod
    def _clean_visitor_id(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("conversation_id", mode="before")
    @classmethod
    def _clean_conversation_id(cls, value: Any) -> str:
        cleaned = ("" if value is None else str(value)).strip()
        return cleaned or "default"


def _detect_web_media_type(mime_type: str, file_name: str) -> MediaType | None:
    if mime_type.startswith("image/"):
        return MediaType.IMAGE
    if (
        mime_type.startswith("audio/")
        or mime_type in _AUDIO_MIME_TYPES
        or file_name.lower().endswith(_AUDIO_EXTENSIONS)
    ):
        return MediaType.AUDIO
    return None


class WebChatAdapter(ChannelAdapter):
    """Channel adapter for the built-in Website Chat HTTP API."""

    channel_name = ChannelType.WEB_CHAT.value
    max_text_length = None
    supports_attachments = True
    delivers_asynchronously = False
    strict_media_validation = True

    def parse_payload_dict(
        self,
        data: dict[str, Any],
        *,
        upload_file: Any = None,
    ) -> tuple[list[UnifiedIncomingMessage], str | None]:
        try:
            parsed = WebChatPayload.model_validate(data or {})
        except Exception as exc:
            msg = str(exc)
            if "Invalid customer ID." in msg:
                raise ChannelValidationError("Invalid customer ID.", status_code=400) from exc
            raise ChannelValidationError("Invalid chat payload.", status_code=400) from exc

        attachments: list[UnifiedAttachment] = []
        if upload_file and getattr(upload_file, "filename", None):
            file_name = secure_filename(upload_file.filename)
            raw_mime = getattr(upload_file, "mimetype", None) or mimetypes.guess_type(file_name)[0] or ""
            mime_type = raw_mime.split(";", 1)[0].strip().lower()
            media_type = _detect_web_media_type(mime_type, file_name)
            if not media_type:
                raise ChannelValidationError("Only image and audio uploads are supported.", status_code=400)
            content = upload_file.read()
            attachments.append(
                UnifiedAttachment(
                    media_type=media_type,
                    file_name=file_name,
                    mime_type=mime_type,
                    size_bytes=len(content) if isinstance(content, (bytes, bytearray)) else None,
                    content=content,
                )
            )

        # Preserve default customer_id=1 when neither customer_id nor visitor_id was specified
        resolved_customer_id = parsed.customer_id
        if resolved_customer_id is None and parsed.visitor_id is None:
            resolved_customer_id = 1

        if parsed.visitor_id:
            external_user_id = parsed.visitor_id
        else:
            external_user_id = f"customer:{resolved_customer_id}"

        incoming = UnifiedIncomingMessage(
            channel=self.channel_name,
            channel_account_id=parsed.channel_account_id,
            external_user_id=external_user_id,
            customer_id=resolved_customer_id,
            conversation_id=parsed.conversation_id,
            text=parsed.message,
            attachments=attachments,
            metadata={"has_visitor_id": bool(parsed.visitor_id)},
        )
        if not incoming.has_content:
            raise ChannelValidationError("Message or media file is required.", status_code=400)

        return [incoming], None

    def parse_incoming(self, req: Request) -> tuple[list[UnifiedIncomingMessage], str | None]:
        is_multipart = req.mimetype == "multipart/form-data"
        data = req.form.to_dict() if is_multipart else (req.get_json(silent=True) or {})
        upload = req.files.get("file") if is_multipart else None
        return self.parse_payload_dict(data, upload_file=upload)

    def download_attachment(
        self,
        attachment: UnifiedAttachment,
        message: UnifiedIncomingMessage,
    ) -> DownloadedMedia:
        if attachment.content is None:
            raise ChannelValidationError("Uploaded media is empty.", status_code=400)
        return DownloadedMedia(
            content=attachment.content,
            mime_type=attachment.mime_type or "",
            file_name=attachment.file_name or "upload.bin",
        )

    def send_message(self, outbound: UnifiedOutboundMessage) -> ChannelDeliveryResult:
        # Web Chat delivers responses synchronously in the HTTP JSON payload.
        return ChannelDeliveryResult(
            success=True,
            chunks_sent=1 if outbound.text else 0,
            delivery_status="sent",
        )

    def format_http_response(
        self,
        results: list[UnifiedAgentResponse],
        *,
        ignored_reason: str | None = None,
    ) -> tuple[Any, int]:
        if not results:
            return {"success": False, "error": ignored_reason or "Empty response"}, 400
        return results[0].to_web_chat_dict(), 200
