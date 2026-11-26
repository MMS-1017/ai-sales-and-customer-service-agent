from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from flask import Request
from pydantic import BaseModel, Field

from app.schemas import UnifiedAgentResponse, UnifiedAttachment, UnifiedIncomingMessage, UnifiedOutboundMessage


class ChannelError(Exception):
    """Base exception raised inside channel adapters."""


class ChannelAuthError(ChannelError):
    """Raised when webhook secret or cryptographic signature validation fails."""

    def __init__(self, message: str = "Unauthorized webhook", status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ChannelValidationError(ChannelError):
    """Raised when an incoming channel payload is structurally invalid."""

    def __init__(self, message: str = "Invalid channel payload", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ChannelDeliveryError(ChannelError):
    """Raised when outbound provider delivery fails."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


@dataclass
class DownloadedMedia:
    """In-memory media bytes and metadata retrieved by an adapter."""

    content: bytes
    mime_type: str
    file_name: str


class ChannelDeliveryResult(BaseModel):
    """Result returned by a ChannelAdapter after delivering an outbound message."""

    success: bool = True
    external_message_id: str | None = None
    chunks_sent: int = 1
    delivery_status: str = "sent"
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def split_text_chunks(text: str, max_length: int | None) -> list[str]:
    """Split a long reply cleanly at line/word boundaries to respect channel limits."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if not max_length or max_length <= 0 or len(cleaned) <= max_length:
        return [cleaned]

    chunks: list[str] = []
    remaining = cleaned
    while len(remaining) > max_length:
        window = remaining[:max_length]
        split_at = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(" "))
        if split_at <= max_length // 4:
            split_at = max_length
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


class ChannelAdapter(ABC):
    """Common interface every messaging channel adapter must implement."""

    channel_name: str = ""
    max_text_length: int | None = 4096
    supports_attachments: bool = True
    delivers_asynchronously: bool = True
    strict_media_validation: bool = False

    def verify_webhook(self, req: Request) -> None:
        """Validate incoming request authenticity. Raise ChannelAuthError on failure."""
        return None

    @abstractmethod
    def parse_incoming(self, req: Request) -> tuple[list[UnifiedIncomingMessage], str | None]:
        """Validate and normalize request data into UnifiedIncomingMessage objects.

        Returns `(messages, ignore_reason)`. If `messages` is empty and `ignore_reason`
        is set, the webhook acknowledges the event cleanly without running the AI agent.
        """

    @abstractmethod
    def download_attachment(
        self,
        attachment: UnifiedAttachment,
        message: UnifiedIncomingMessage,
    ) -> DownloadedMedia:
        """Retrieve raw bytes + metadata for a normalized attachment."""

    @abstractmethod
    def send_message(self, outbound: UnifiedOutboundMessage) -> ChannelDeliveryResult:
        """Deliver an outbound response through the channel provider."""

    def format_http_response(
        self,
        results: list[UnifiedAgentResponse],
        *,
        ignored_reason: str | None = None,
    ) -> tuple[Any, int]:
        """Build the HTTP response tuple `(body, status_code)` for this channel's endpoint."""
        if ignored_reason:
            return {"status": "ignored", "reason": ignored_reason}, 200
        return {"status": "processed"}, 200
