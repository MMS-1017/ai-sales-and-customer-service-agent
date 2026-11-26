from __future__ import annotations

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
from app.services.facebook_service import FacebookService

logger = logging.getLogger(__name__)


class MessengerAttachmentPayload(BaseModel):
    url: str | None = None
    model_config = ConfigDict(extra="allow")


class MessengerAttachment(BaseModel):
    type: str = ""
    payload: MessengerAttachmentPayload = Field(default_factory=MessengerAttachmentPayload)
    model_config = ConfigDict(extra="allow")


class MessengerMessagePayload(BaseModel):
    mid: str | None = None
    text: str | None = ""
    is_echo: bool = False
    attachments: list[MessengerAttachment] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")


def _guess_extension_from_mime(mime_type: str, media_type: MediaType) -> str:
    ext = mimetypes.guess_extension(mime_type)
    if ext:
        return ext
    if "mp4" in mime_type:
        return ".mp4"
    if "ogg" in mime_type or "opus" in mime_type:
        return ".ogg"
    if "wav" in mime_type:
        return ".wav"
    if "webm" in mime_type:
        return ".webm"
    return ".jpg" if media_type == MediaType.IMAGE else ".mp4"


class MessengerAdapter(ChannelAdapter):
    """Channel adapter for Facebook Messenger via Meta Graph Webhooks."""

    channel_name = ChannelType.MESSENGER.value
    max_text_length = 2000
    supports_attachments = True
    delivers_asynchronously = True
    strict_media_validation = False

    def verify_webhook(self, req: Request) -> None:
        raw_body = req.get_data()
        signature = req.headers.get("X-Hub-Signature-256")
        require_secret = current_app.config.get("REQUIRE_WEBHOOK_SECRETS", False)
        if not FacebookService.verify_signature(
            raw_body,
            signature,
            allow_unconfigured=not require_secret,
        ):
            raise ChannelAuthError("Invalid webhook signature.", status_code=403)

    def verify_subscription_challenge(self, req: Request) -> tuple[str, int]:
        """Handle Meta GET webhook verification handshake."""
        mode = req.args.get("hub.mode")
        token = req.args.get("hub.verify_token")
        challenge = req.args.get("hub.challenge") or ""
        expected_token = current_app.config.get("FACEBOOK_VERIFY_TOKEN")
        if mode == "subscribe" and expected_token and token == expected_token:
            return challenge, 200
        return "Forbidden", 403

    def parse_payload_dict(self, data: dict[str, Any]) -> tuple[list[UnifiedIncomingMessage], str | None]:
        """Normalize a Meta Messenger webhook payload into UnifiedIncomingMessage objects."""
        if data.get("object") != "page":
            raise ChannelValidationError("Invalid webhook object.", status_code=400)

        messages: list[UnifiedIncomingMessage] = []
        for entry in data.get("entry") or []:
            page_id = str(entry.get("id") or "").strip()
            for event in entry.get("messaging") or []:
                msg_raw = event.get("message")
                if not isinstance(msg_raw, dict):
                    # Delivery receipts / read events without a message object
                    continue
                parsed_msg = MessengerMessagePayload.model_validate(msg_raw)
                if parsed_msg.is_echo:
                    continue

                sender_id = str((event.get("sender") or {}).get("id") or "").strip()
                if not sender_id:
                    continue

                attachments: list[UnifiedAttachment] = []
                for att in parsed_msg.attachments:
                    att_type = (att.type or "").lower()
                    if att_type in ("image", "audio", "video"):
                        media_type = MediaType.AUDIO if att_type in ("audio", "video") else MediaType.IMAGE
                        attachments.append(
                            UnifiedAttachment(
                                media_type=media_type,
                                url=att.payload.url,
                                metadata={"att_type": att_type},
                            )
                        )

                incoming = UnifiedIncomingMessage(
                    external_message_id=str(parsed_msg.mid) if parsed_msg.mid is not None else None,
                    channel=self.channel_name,
                    channel_account_id=page_id,
                    external_user_id=sender_id,
                    conversation_id=f"{self.channel_name}:{sender_id}",
                    text=parsed_msg.text or "",
                    attachments=attachments,
                    timestamp=event.get("timestamp"),
                    metadata={"page_id": page_id} if page_id else {},
                )
                if incoming.has_content:
                    messages.append(incoming)

        if not messages:
            return [], "no_processable_messages"
        return messages, None

    def parse_incoming(self, req: Request) -> tuple[list[UnifiedIncomingMessage], str | None]:
        data = req.get_json(silent=True) or {}
        return self.parse_payload_dict(data)

    def download_attachment(
        self,
        attachment: UnifiedAttachment,
        message: UnifiedIncomingMessage,
    ) -> DownloadedMedia:
        if not attachment.url:
            raise ValueError("Messenger attachment is missing download URL.")
        res = requests.get(attachment.url, timeout=30)
        res.raise_for_status()
        raw_mime = res.headers.get("Content-Type", "")
        mime_type = raw_mime.split(";", 1)[0].strip().lower()
        ext = _guess_extension_from_mime(mime_type, attachment.media_type)
        file_name = attachment.file_name or f"fb_{message.external_user_id}_{attachment.media_type.value}{ext}"
        return DownloadedMedia(content=res.content, mime_type=mime_type, file_name=file_name)

    def send_message(self, outbound: UnifiedOutboundMessage) -> ChannelDeliveryResult:
        text_to_send = (outbound.text or "").strip()
        if not text_to_send and outbound.attachments:
            urls = [att.url for att in outbound.attachments if att.url]
            text_to_send = "\n".join(urls) if urls else "[Media attachment]"

        chunks = split_text_chunks(text_to_send, self.max_text_length)
        if not chunks:
            return ChannelDeliveryResult(success=True, chunks_sent=0, delivery_status="skipped")

        last_response: dict[str, Any] = {}
        try:
            for chunk in chunks:
                res = FacebookService.send_message(outbound.recipient_id, chunk)
                if isinstance(res, dict):
                    last_response = res
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            retryable = status is None or status >= 500 or status == 429
            raise ChannelDeliveryError(
                f"Messenger Graph API error (status={status}): {exc}",
                retryable=retryable,
                status_code=status,
            ) from exc
        except requests.RequestException as exc:
            raise ChannelDeliveryError(f"Messenger network error: {exc}", retryable=True) from exc
        except Exception as exc:
            raise ChannelDeliveryError(f"Messenger delivery error: {exc}", retryable=False) from exc

        return ChannelDeliveryResult(
            success=True,
            external_message_id=last_response.get("message_id"),
            chunks_sent=len(chunks),
            delivery_status="sent",
            metadata={"provider_response": last_response},
        )

    def format_http_response(
        self,
        results: list[UnifiedAgentResponse],
        *,
        ignored_reason: str | None = None,
    ) -> tuple[Any, int]:
        return "EVENT_RECEIVED", 200
