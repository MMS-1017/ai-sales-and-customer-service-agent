from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid

from flask import has_app_context
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Conversation, Customer, Message, MessageAttachment
from app.schemas import (
    UnifiedAttachment,
    UnifiedIncomingMessage,
    UnifiedMediaRecord,
    UnifiedOutboundMessage,
    normalize_channel_name,
)

logger = logging.getLogger(__name__)


class DuplicateMessageError(ValueError):
    """Raised when an external inbound message ID has already been persisted."""


class ConversationService:
    """Manages persistent omnichannel conversations, messages, idempotency, and context."""

    MAX_HISTORY: int = 20
    MAX_CONVERSATIONS: int = 1000
    _conversations: dict[str, list[str]] = {}

    @classmethod
    def resolve_or_create_conversation(
        cls,
        *,
        customer_id: int,
        channel: str,
        external_conversation_id: str,
        channel_account_id: str = "",
        metadata: dict | None = None,
    ) -> Conversation:
        norm_channel = normalize_channel_name(channel)
        account = (channel_account_id or "").strip()
        ext_conv_id = external_conversation_id.strip()

        conv = Conversation.query.filter_by(
            channel=norm_channel,
            channel_account_id=account,
            external_conversation_id=ext_conv_id,
        ).first()

        if conv:
            conv.last_message_at = datetime.now(timezone.utc)
            if metadata:
                merged = dict(conv.metadata_json or {})
                merged.update(metadata)
                conv.metadata_json = merged
            db.session.flush()
            return conv

        try:
            conv = Conversation(
                customer_id=customer_id,
                channel=norm_channel,
                channel_account_id=account,
                external_conversation_id=ext_conv_id,
                status="open",
                metadata_json=metadata or {},
            )
            db.session.add(conv)
            db.session.commit()
            return conv
        except IntegrityError:
            db.session.rollback()
            conv = Conversation.query.filter_by(
                channel=norm_channel,
                channel_account_id=account,
                external_conversation_id=ext_conv_id,
            ).first()
            if conv:
                return conv
            raise

    @staticmethod
    def has_processed_external_message(
        *,
        channel: str,
        channel_account_id: str = "",
        external_message_id: str | None = None,
    ) -> bool:
        if not external_message_id:
            return False
        norm_channel = normalize_channel_name(channel)
        account = (channel_account_id or "").strip()
        found = (
            Message.query
            .filter_by(
                channel=norm_channel,
                channel_account_id=account,
                external_message_id=str(external_message_id),
                direction="inbound",
            )
            .first()
        )
        return found is not None

    @staticmethod
    def record_inbound_message(
        *,
        conversation: Conversation,
        incoming: UnifiedIncomingMessage,
        full_content: str,
        media_records: list[UnifiedMediaRecord] | None = None,
        attachments: list[UnifiedAttachment] | None = None,
    ) -> Message:
        """Persist an inbound customer message and its attachments atomically."""
        media_records = media_records or []
        attachments = attachments or []

        msg = Message(
            internal_id=incoming.id,
            conversation_id=conversation.id,
            customer_id=conversation.customer_id,
            channel=incoming.channel,
            channel_account_id=incoming.channel_account_id,
            direction="inbound",
            role="customer",
            external_message_id=incoming.external_message_id,
            message_type=incoming.message_type.value,
            content=full_content,
            delivery_status="received",
            provider_timestamp=incoming.timestamp,
            metadata_json=incoming.metadata or {},
        )
        try:
            db.session.add(msg)
            db.session.flush()

            for idx, att in enumerate(attachments):
                matched_record = media_records[idx] if idx < len(media_records) else None
                db.session.add(
                    MessageAttachment(
                        message_id=msg.id,
                        media_file_id=matched_record.id if matched_record else None,
                        media_type=att.media_type.value,
                        file_name=matched_record.file_name if matched_record else att.file_name,
                        mime_type=att.mime_type,
                        external_url=att.url,
                        extracted_text=att.extracted_text,
                        metadata_json={},
                    )
                )

            conversation.last_message_at = datetime.now(timezone.utc)
            db.session.commit()
            return msg
        except IntegrityError as exc:
            db.session.rollback()
            if incoming.external_message_id:
                raise DuplicateMessageError(
                    f"Duplicate external_message_id={incoming.external_message_id}"
                ) from exc
            raise

    @staticmethod
    def record_outbound_message(
        *,
        conversation: Conversation,
        outbound: UnifiedOutboundMessage,
        delivery_status: str = "pending",
        external_message_id: str | None = None,
        metadata: dict | None = None,
    ) -> Message:
        """Persist an outbound agent message record."""
        merged_meta = dict(outbound.metadata or {})
        if outbound.reply_to_external_message_id:
            merged_meta["reply_to_external_message_id"] = outbound.reply_to_external_message_id
        if metadata:
            merged_meta.update(metadata)

        msg = Message(
            internal_id=outbound.id,
            conversation_id=conversation.id,
            customer_id=conversation.customer_id,
            channel=outbound.channel,
            channel_account_id=outbound.channel_account_id,
            direction="outbound",
            role="assistant",
            external_message_id=external_message_id,
            message_type="mixed" if outbound.attachments else "text",
            content=outbound.text,
            delivery_status=delivery_status,
            provider_timestamp=datetime.now(timezone.utc),
            metadata_json=merged_meta,
        )
        db.session.add(msg)
        conversation.last_message_at = datetime.now(timezone.utc)
        db.session.commit()
        return msg

    @staticmethod
    def update_outbound_delivery(
        message_record: Message,
        *,
        delivery_status: str,
        external_message_id: str | None = None,
        metadata_updates: dict | None = None,
    ) -> None:
        message_record.delivery_status = delivery_status
        if external_message_id:
            message_record.external_message_id = external_message_id
        if metadata_updates:
            merged = dict(message_record.metadata_json or {})
            merged.update(metadata_updates)
            message_record.metadata_json = merged
        db.session.commit()

    @staticmethod
    def find_sent_outbound_reply(
        *,
        conversation_id: int,
        reply_to_external_message_id: str | None,
    ) -> Message | None:
        if not reply_to_external_message_id:
            return None
        candidates = (
            Message.query
            .filter_by(
                conversation_id=conversation_id,
                direction="outbound",
                delivery_status="sent",
            )
            .order_by(Message.id.desc())
            .limit(20)
            .all()
        )
        for msg in candidates:
            if (msg.metadata_json or {}).get("reply_to_external_message_id") == reply_to_external_message_id:
                return msg
        return None

    @classmethod
    def get_conversation_history(cls, conversation_id: int, limit: int | None = None) -> list[str]:
        """Return alternating content history strings from PostgreSQL for LangGraph."""
        max_items = limit or cls.MAX_HISTORY
        recent = (
            Message.query
            .filter_by(conversation_id=conversation_id)
            .order_by(Message.id.desc())
            .limit(max_items)
            .all()
        )
        recent.reverse()
        return [m.content for m in recent if m.content]

    @staticmethod
    def get_cross_channel_context(
        *,
        customer_id: int,
        current_conversation_id: int,
        max_conversations: int = 3,
        max_messages_per_conv: int = 4,
    ) -> list[str]:
        """Retrieve concise read-only context snippets from the customer's OTHER channel threads."""
        other_conversations = (
            Conversation.query
            .filter(
                Conversation.customer_id == customer_id,
                Conversation.id != current_conversation_id,
            )
            .order_by(Conversation.last_message_at.desc())
            .limit(max_conversations)
            .all()
        )
        snippets: list[str] = []
        for conv in other_conversations:
            msgs = (
                Message.query
                .filter_by(conversation_id=conv.id)
                .order_by(Message.id.desc())
                .limit(max_messages_per_conv)
                .all()
            )
            if not msgs:
                continue
            msgs.reverse()
            turns = " | ".join(
                f"{'Customer' if m.role == 'customer' else 'Agent'}: {m.content[:180]}"
                for m in msgs
                if m.content
            )
            if turns:
                ts_label = (
                    conv.last_message_at.strftime("%Y-%m-%d %H:%M UTC")
                    if conv.last_message_at
                    else "recent"
                )
                snippets.append(f"[{conv.channel} thread @ {ts_label}]: {turns}")
        return snippets

    # ------------------------------------------------------------------
    # Legacy string-keyed compatibility helpers (DB-backed when possible)
    # ------------------------------------------------------------------
    @classmethod
    def get_history(cls, conversation_id: str) -> list[str]:
        if has_app_context():
            try:
                conv = Conversation.query.filter_by(external_conversation_id=str(conversation_id)).first()
                if conv:
                    return cls.get_conversation_history(conv.id)
            except Exception:
                pass
        return cls._conversations.get(conversation_id, []).copy()

    @classmethod
    def add_message(cls, conversation_id: str, message: str) -> None:
        if conversation_id not in cls._conversations:
            if len(cls._conversations) >= cls.MAX_CONVERSATIONS:
                oldest_key = next(iter(cls._conversations))
                cls._conversations.pop(oldest_key, None)
            cls._conversations[conversation_id] = []

        cls._conversations[conversation_id].append(message)
        if len(cls._conversations[conversation_id]) > cls.MAX_HISTORY:
            cls._conversations[conversation_id] = cls._conversations[conversation_id][-cls.MAX_HISTORY:]

    @classmethod
    def clear(cls, conversation_id: str | None = None) -> None:
        if conversation_id is None:
            cls._conversations.clear()
            return
        cls._conversations.pop(conversation_id, None)
