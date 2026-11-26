from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from app.models import Conversation
from app.schemas import UnifiedOutboundMessage
from app.services.conversation_service import ConversationService

if TYPE_CHECKING:
    from app.channels import ChannelDeliveryResult, ChannelRegistry

logger = logging.getLogger(__name__)


class OutboundMessagingService:
    """Delivers agent responses through the target ChannelAdapter with idempotency and retries."""

    @classmethod
    def send(
        cls,
        outbound: UnifiedOutboundMessage,
        *,
        conversation: Conversation | None = None,
        registry: ChannelRegistry | None = None,
        max_retries: int = 2,
        retry_backoff_base: float = 0.25,
    ) -> ChannelDeliveryResult:
        from app.channels import ChannelDeliveryError, ChannelDeliveryResult, get_channel_registry

        adapter = (registry or get_channel_registry()).get(outbound.channel)

        # Duplicate outbound guard: avoid re-sending an already delivered reply for the same turn
        if conversation and outbound.reply_to_external_message_id:
            already_sent = ConversationService.find_sent_outbound_reply(
                conversation_id=conversation.id,
                reply_to_external_message_id=outbound.reply_to_external_message_id,
            )
            if already_sent:
                logger.info(
                    "Skipping duplicate outbound delivery for channel=%s conv=%s reply_to=%s",
                    outbound.channel,
                    conversation.id,
                    outbound.reply_to_external_message_id,
                )
                return ChannelDeliveryResult(
                    success=True,
                    external_message_id=already_sent.external_message_id,
                    delivery_status="already_sent",
                )

        msg_record = None
        if conversation is not None:
            msg_record = ConversationService.record_outbound_message(
                conversation=conversation,
                outbound=outbound,
                delivery_status="pending",
            )

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                result = adapter.send_message(outbound)
                if msg_record is not None:
                    ConversationService.update_outbound_delivery(
                        msg_record,
                        delivery_status=result.delivery_status,
                        external_message_id=result.external_message_id,
                        metadata_updates={"chunks_sent": result.chunks_sent},
                    )
                return result
            except ChannelDeliveryError as exc:
                last_error = exc
                should_retry = exc.retryable and attempt < max_retries
                logger.warning(
                    "Outbound delivery failure (attempt=%s/%s, channel=%s, retryable=%s): %s",
                    attempt + 1,
                    max_retries + 1,
                    outbound.channel,
                    exc.retryable,
                    exc,
                )
                if should_retry:
                    if retry_backoff_base > 0:
                        time.sleep(retry_backoff_base * (2 ** attempt))
                    continue
                break
            except Exception as exc:
                last_error = exc
                logger.error("Unexpected outbound delivery error on channel=%s: %s", outbound.channel, exc)
                break

        err_text = str(last_error) if last_error else "Delivery failed"
        if msg_record is not None:
            ConversationService.update_outbound_delivery(
                msg_record,
                delivery_status="failed",
                metadata_updates={"delivery_error": err_text},
            )
        return ChannelDeliveryResult(
            success=False,
            chunks_sent=0,
            delivery_status="failed",
            error=err_text,
        )
