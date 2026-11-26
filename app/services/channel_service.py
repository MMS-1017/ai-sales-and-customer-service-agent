from __future__ import annotations

import collections
import logging
import threading
from typing import TYPE_CHECKING

from app.agent import agent_graph
from app.extensions import db
from app.schemas import (
    UnifiedAgentResponse,
    UnifiedIncomingMessage,
    UnifiedMediaRecord,
    UnifiedOutboundMessage,
)
from app.services.conversation_service import ConversationService, DuplicateMessageError
from app.services.identity_service import CustomerIdentityService, CustomerNotFoundError
from app.services.media_service import MediaService
from app.services.outbound_service import OutboundMessagingService

if TYPE_CHECKING:
    from app.channels import ChannelAdapter, ChannelRegistry

logger = logging.getLogger(__name__)


class WebhookDeduplicator:
    """Thread-safe bounded in-memory fast cache in front of DB external_message_id idempotency."""

    def __init__(self, maxsize: int = 2000):
        self._maxsize = maxsize
        self._seen: set[str] = set()
        self._order: collections.deque[str] = collections.deque()
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

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()
            self._order.clear()


class ChannelService:
    """Channel-agnostic omnichannel orchestration service."""

    @staticmethod
    def resolve_customer(incoming: UnifiedIncomingMessage):
        """Resolve or create an internal Customer via CustomerIdentityService."""
        customer, _ = CustomerIdentityService.resolve_or_create_customer(incoming)
        return customer

    @classmethod
    def process_message(
        cls,
        incoming: UnifiedIncomingMessage,
        *,
        adapter: ChannelAdapter | None = None,
        registry: ChannelRegistry | None = None,
        deliver_outbound: bool = True,
    ) -> UnifiedAgentResponse:
        """Execute the unified omnichannel pipeline without channel-specific branching."""
        from app.channels import get_channel_registry

        resolved_registry = registry or get_channel_registry()
        resolved_adapter = adapter or resolved_registry.get(incoming.channel)

        # 1. Persistent database-level idempotency check
        if incoming.external_message_id and ConversationService.has_processed_external_message(
            channel=incoming.channel,
            channel_account_id=incoming.channel_account_id,
            external_message_id=incoming.external_message_id,
        ):
            logger.info(
                "DB idempotency hit: skipping duplicate inbound channel=%s external_id=%s",
                incoming.channel,
                incoming.external_message_id,
            )
            return UnifiedAgentResponse(
                success=True,
                channel=incoming.channel,
                conversation_id=incoming.conversation_id,
                customer_id=incoming.customer_id or 0,
                response="",
                reply_to_message_id=incoming.external_message_id,
                delivery_status="duplicate_ignored",
                error="duplicate_message",
            )

        # 2. Identity Resolution
        customer, _ = CustomerIdentityService.resolve_or_create_customer(incoming)

        # 3. Attachment Retrieval & Multi-modal Analysis (delegated cleanly to adapter + MediaService)
        media_context: list[str] = []
        media_records: list[UnifiedMediaRecord] = []

        for att in incoming.attachments:
            label = "Image analysis" if att.media_type.value == "image" else "Audio transcription"
            try:
                downloaded = resolved_adapter.download_attachment(att, incoming)
                record, extracted_text = MediaService.save_and_process(
                    file_name=downloaded.file_name,
                    content=downloaded.content,
                    mime_type=downloaded.mime_type,
                    media_type=att.media_type.value,
                    customer_id=customer.id,
                    source=incoming.channel,
                )
                att.extracted_text = extracted_text
                media_records.append(
                    UnifiedMediaRecord(
                        id=record.id,
                        media_type=att.media_type,
                        file_name=record.file_name,
                        media_url=f"/api/media/{record.id}",
                        download_url=f"/api/media/{record.id}?download=1",
                        raw_url=f"/api/media/{record.id}/raw",
                    )
                )
                if extracted_text:
                    media_context.append(f"[{label}: {extracted_text}]")
                elif not resolved_adapter.strict_media_validation and not incoming.text:
                    media_context.append(f"[Customer sent a {att.media_type.value}]")
            except ValueError:
                if resolved_adapter.strict_media_validation:
                    raise
                logger.warning("Validation error processing %s media attachment", incoming.channel)
                if not incoming.text:
                    media_context.append(
                        f"The customer sent a {att.media_type.value}, "
                        "but media processing could not be completed."
                    )
            except Exception as err:
                if resolved_adapter.strict_media_validation:
                    raise
                logger.warning("Failed to download/process %s media: %s", incoming.channel, err)
                if not incoming.text:
                    media_context.append(
                        f"The customer sent a {att.media_type.value}, "
                        "but media processing could not be completed."
                    )

        parts = [part for part in [incoming.text] + media_context if part]
        full_message = "\n".join(parts).strip()

        if not full_message and incoming.attachments:
            primary_type = incoming.attachments[0].media_type.value
            full_message = f"The customer uploaded a {primary_type}."

        if not full_message:
            return UnifiedAgentResponse(
                success=False,
                channel=incoming.channel,
                conversation_id=incoming.conversation_id,
                customer_id=customer.id,
                response="",
                media_records=media_records,
                reply_to_message_id=incoming.external_message_id,
                delivery_status="ignored",
                error="empty_message",
            )

        # 4. Conversation Resolution & History Assembly (before adding the new inbound message)
        conversation = ConversationService.resolve_or_create_conversation(
            customer_id=customer.id,
            channel=incoming.channel,
            external_conversation_id=incoming.conversation_id,
            channel_account_id=incoming.channel_account_id,
        )
        history = ConversationService.get_conversation_history(conversation.id)
        cross_channel_context = ConversationService.get_cross_channel_context(
            customer_id=customer.id,
            current_conversation_id=conversation.id,
        )

        # 5. Persist Inbound Message (unique index guards concurrent duplicates)
        try:
            inbound_record = ConversationService.record_inbound_message(
                conversation=conversation,
                incoming=incoming,
                full_content=full_message,
                media_records=media_records,
                attachments=incoming.attachments,
            )
        except DuplicateMessageError:
            return UnifiedAgentResponse(
                success=True,
                channel=incoming.channel,
                conversation_id=incoming.conversation_id,
                db_conversation_id=conversation.id,
                customer_id=customer.id,
                response="",
                reply_to_message_id=incoming.external_message_id,
                delivery_status="duplicate_ignored",
                error="duplicate_message",
            )

        # 6. Execute Unified Channel-Independent LangGraph AI Agent
        result = agent_graph.invoke(
            {
                "messages": history + [full_message],
                "customer_id": customer.id,
                "customer_profile": {"name": customer.name},
                "cross_channel_context": cross_channel_context,
            }
        )

        raw_response = result.get("response")
        if resolved_adapter.delivers_asynchronously:
            response_text = (raw_response or "Sorry, I couldn't process your request.").strip()
        else:
            response_text = raw_response if raw_response is not None else ""

        # 7. Persist Outbound Message & Deliver via Target Adapter
        outbound = UnifiedOutboundMessage(
            channel=incoming.channel,
            channel_account_id=incoming.channel_account_id,
            recipient_id=incoming.external_user_id,
            conversation_id=conversation.id,
            text=response_text,
            reply_to_external_message_id=incoming.external_message_id,
        )

        delivery_status = "sent"
        outbound_ext_id = None
        if deliver_outbound and resolved_adapter.delivers_asynchronously:
            delivery = OutboundMessagingService.send(
                outbound,
                conversation=conversation,
                registry=resolved_registry,
            )
            delivery_status = delivery.delivery_status
            outbound_ext_id = delivery.external_message_id
        else:
            ConversationService.record_outbound_message(
                conversation=conversation,
                outbound=outbound,
                delivery_status="sent",
            )

        inbound_record.delivery_status = "processed"
        db.session.commit()

        return UnifiedAgentResponse(
            success=True,
            channel=incoming.channel,
            conversation_id=incoming.conversation_id,
            db_conversation_id=conversation.id,
            customer_id=customer.id,
            response=response_text,
            intent=result.get("intent"),
            tool_result=result.get("tool_result"),
            media_records=media_records,
            reply_to_message_id=incoming.external_message_id,
            outbound_message_id=outbound_ext_id,
            delivery_status=delivery_status,
        )
