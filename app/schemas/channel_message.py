from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ChannelType(str, Enum):
    """Canonical built-in channel identifiers (future channels can also pass str slugs)."""

    WHATSAPP = "whatsapp"
    MESSENGER = "facebook"
    WEB_CHAT = "web_chat"

    @classmethod
    def _missing_(cls, value: object) -> ChannelType | None:
        if isinstance(value, str):
            normalized = value.strip().lower()
            aliases = {
                "whatsapp": cls.WHATSAPP,
                "wa": cls.WHATSAPP,
                "facebook": cls.MESSENGER,
                "fb": cls.MESSENGER,
                "messenger": cls.MESSENGER,
                "facebook_messenger": cls.MESSENGER,
                "web": cls.WEB_CHAT,
                "web_chat": cls.WEB_CHAT,
                "webchat": cls.WEB_CHAT,
                "website": cls.WEB_CHAT,
            }
            return aliases.get(normalized)
        return None


def normalize_channel_name(value: Any) -> str:
    """Normalize known channel aliases to canonical names while preserving future channel slugs."""
    if isinstance(value, ChannelType):
        return value.value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Channel identifier must be a non-empty string.")
    cleaned = value.strip().lower()
    matched = ChannelType._missing_(cleaned)
    return matched.value if matched else cleaned


def normalize_timestamp(value: Any) -> datetime:
    """Normalize ISO strings, Unix epoch seconds/milliseconds, or naive datetimes to UTC."""
    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        # Auto-detect millisecond epoch timestamps (> year 2001 in ms)
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if raw.isdigit():
            return normalize_timestamp(int(raw))
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    raise ValueError(f"Unsupported timestamp format: {value!r}")


class MediaType(str, Enum):
    """Supported normalized media attachment categories."""

    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class MessageType(str, Enum):
    """Normalized high-level message categories."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    MIXED = "mixed"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> MessageType | None:
        if isinstance(value, str):
            norm = value.strip().lower()
            if norm in {"ptt", "voice", "audio_message"}:
                return cls.AUDIO
            if norm in {"image_message", "photo"}:
                return cls.IMAGE
            if norm in {"chat", "text_message"}:
                return cls.TEXT
            if norm in {"file", "doc"}:
                return cls.DOCUMENT
            for member in cls:
                if member.value == norm:
                    return member
            return cls.UNKNOWN
        return None


class UnifiedAttachment(BaseModel):
    """Normalized media attachment across all messaging channels."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    media_type: MediaType
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    content: bytes | None = None
    url: str | None = None
    extracted_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")


class UnifiedIncomingMessage(BaseModel):
    """Standardized channel-agnostic inbound message contract."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    external_message_id: str | None = None
    channel: str
    channel_account_id: str = ""
    external_user_id: str
    customer_id: int | None = None
    conversation_id: str
    message_type: MessageType = MessageType.TEXT
    text: str = ""
    attachments: list[UnifiedAttachment] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _support_legacy_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            normalized = dict(data)
            if "external_user_id" not in normalized and "sender_id" in normalized:
                normalized["external_user_id"] = normalized["sender_id"]
            if "external_message_id" not in normalized and "message_id" in normalized:
                normalized["external_message_id"] = normalized["message_id"]
            return normalized
        return data

    @field_validator("channel", mode="before")
    @classmethod
    def _validate_channel(cls, value: Any) -> str:
        return normalize_channel_name(value)

    @field_validator("channel_account_id", mode="before")
    @classmethod
    def _normalize_account_id(cls, value: Any) -> str:
        return ("" if value is None else str(value)).strip()

    @field_validator("external_user_id", mode="before")
    @classmethod
    def _validate_external_user_id(cls, value: Any) -> str:
        cleaned = ("" if value is None else str(value)).strip()
        if not cleaned:
            raise ValueError("external_user_id must not be empty.")
        return cleaned

    @field_validator("text", mode="before")
    @classmethod
    def _strip_text(cls, value: Any) -> str:
        return ("" if value is None else str(value)).strip()

    @field_validator("timestamp", mode="before")
    @classmethod
    def _parse_timestamp(cls, value: Any) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def _infer_message_type_and_defaults(self) -> UnifiedIncomingMessage:
        if not self.conversation_id or not self.conversation_id.strip():
            self.conversation_id = f"{self.channel}:{self.external_user_id}"

        # Normalize message_type reliably when attachments exist
        if self.attachments:
            if self.text:
                self.message_type = MessageType.MIXED
            elif self.message_type in (MessageType.TEXT, MessageType.UNKNOWN):
                first_type = self.attachments[0].media_type
                self.message_type = MessageType(first_type.value)
        elif self.text and self.message_type == MessageType.UNKNOWN:
            self.message_type = MessageType.TEXT

        return self

    @property
    def sender_id(self) -> str:
        """Backward-compatible alias for external_user_id."""
        return self.external_user_id

    @property
    def message_id(self) -> str | None:
        """Backward-compatible alias for external_message_id."""
        return self.external_message_id

    @property
    def has_content(self) -> bool:
        """True when the normalized message carries text or at least one attachment."""
        return bool(self.text or self.attachments)


class UnifiedOutboundMessage(BaseModel):
    """Standardized channel-agnostic outbound message contract."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: str
    channel_account_id: str = ""
    recipient_id: str
    conversation_id: int | str
    text: str
    attachments: list[UnifiedAttachment] = Field(default_factory=list)
    reply_to_external_message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")

    @field_validator("channel", mode="before")
    @classmethod
    def _validate_channel(cls, value: Any) -> str:
        return normalize_channel_name(value)


class UnifiedMediaRecord(BaseModel):
    """Normalized persisted media asset returned to callers/UI."""

    id: int
    media_type: MediaType
    file_name: str
    media_url: str
    download_url: str
    raw_url: str


class UnifiedAgentResponse(BaseModel):
    """Normalized pipeline result returned after handling a UnifiedIncomingMessage."""

    success: bool = True
    channel: str
    conversation_id: str
    db_conversation_id: int | None = None
    customer_id: int
    response: str
    intent: str | None = None
    tool_result: Any = None
    media_records: list[UnifiedMediaRecord] = Field(default_factory=list)
    reply_to_message_id: str | None = None
    outbound_message_id: str | None = None
    delivery_status: str = "pending"
    error: str | None = None

    def to_web_chat_dict(self) -> dict[str, Any]:
        """Serialize into the JSON response shape expected by the Web Chat UI."""
        payload: dict[str, Any] = {
            "success": self.success,
            "conversation_id": self.conversation_id,
            "customer_id": self.customer_id,
            "response": self.response,
            "intent": self.intent,
            "tool_result": self.tool_result,
            "delivery_status": self.delivery_status,
        }
        if self.media_records:
            primary = self.media_records[0]
            payload["media_id"] = primary.id
            payload["media_url"] = primary.media_url
            payload["media_type"] = primary.media_type.value
            payload["media_name"] = primary.file_name
            payload["download_url"] = primary.download_url
            payload["raw_url"] = primary.raw_url
        return payload
