from __future__ import annotations

import logging
import re

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Conversation,
    Customer,
    CustomerChannelIdentity,
    MediaFile,
    Message,
    Order,
)
from app.schemas import UnifiedIncomingMessage, normalize_channel_name

logger = logging.getLogger(__name__)


class CustomerNotFoundError(LookupError):
    """Raised when an explicitly referenced Customer does not exist."""


class IdentityConflictError(ValueError):
    """Raised when a channel identity is already bound to a different Customer."""


def _sanitize_identifier_for_email(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", value.strip())
    return (cleaned or "user")[:180]


def _candidate_legacy_emails(channel: str, external_user_id: str) -> tuple[str, list[str]]:
    """Build primary synthetic email and any legacy emails to prevent duplicate customer rows."""
    if channel == "whatsapp":
        normalized = external_user_id.split("@", 1)[0].lstrip("+")
        primary = f"whatsapp_{_sanitize_identifier_for_email(normalized)}@whatsapp.local"
        return primary, [primary]
    if channel == "facebook":
        primary = f"facebook_{_sanitize_identifier_for_email(external_user_id)}@facebook.local"
        return primary, [primary]
    safe = _sanitize_identifier_for_email(external_user_id)
    primary = f"{channel}_{safe}@{channel}.local"
    return primary, [primary]


def _default_display_name(channel: str, external_user_id: str, metadata: dict) -> str:
    for key in ("sender_name", "profile_name", "display_name", "name"):
        val = metadata.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:120]
    pretty_channel = {
        "whatsapp": "WhatsApp Customer",
        "facebook": "Facebook User",
        "web_chat": "Web Visitor",
    }.get(channel, f"{channel.title()} User")
    short_id = external_user_id.split("@", 1)[0][:40]
    return f"{pretty_channel} {short_id}".strip()


class CustomerIdentityService:
    """Manages unified internal Customer resolution and cross-channel identity linking."""

    @staticmethod
    def find_identity(
        channel: str,
        external_user_id: str,
        channel_account_id: str = "",
    ) -> CustomerChannelIdentity | None:
        norm_channel = normalize_channel_name(channel)
        account = (channel_account_id or "").strip()
        ext_id = external_user_id.strip()

        exact = CustomerChannelIdentity.query.filter_by(
            channel=norm_channel,
            channel_account_id=account,
            external_user_id=ext_id,
        ).first()
        if exact:
            return exact

        # If incoming event is scoped to an account, fall back only to an account-agnostic identity
        if account:
            return CustomerChannelIdentity.query.filter_by(
                channel=norm_channel,
                channel_account_id="",
                external_user_id=ext_id,
            ).first()

        return None

    @classmethod
    def resolve_or_create_customer(
        cls,
        incoming: UnifiedIncomingMessage,
    ) -> tuple[Customer, CustomerChannelIdentity | None]:
        """Resolve an existing Customer safely or create one without unreliable auto-merging."""
        norm_channel = normalize_channel_name(incoming.channel)
        account = (incoming.channel_account_id or "").strip()
        ext_id = incoming.external_user_id.strip()

        # 1. Explicit pre-resolved internal customer_id (e.g. authenticated Website session)
        if incoming.customer_id is not None:
            customer = db.session.get(Customer, incoming.customer_id)
            if not customer:
                raise CustomerNotFoundError("Customer not found.")

            identity = cls.find_identity(norm_channel, ext_id, account)
            if identity is None and incoming.metadata.get("has_visitor_id"):
                try:
                    identity = cls.link_identity(
                        customer_id=customer.id,
                        channel=norm_channel,
                        external_user_id=ext_id,
                        channel_account_id=account,
                        display_name=customer.name,
                        verified=False,
                    )
                except IdentityConflictError:
                    # Never silently hijack/merge an identity owned by another customer
                    logger.warning(
                        "Visitor identity %s:%s already linked to another customer; keeping explicit customer_id=%s",
                        norm_channel,
                        ext_id,
                        customer.id,
                    )
            return customer, identity

        # 2. Look up existing linked channel identity
        identity = cls.find_identity(norm_channel, ext_id, account)
        if identity and identity.customer:
            return identity.customer, identity

        # 3. Legacy customer email check + new customer creation (atomic against races)
        primary_email, legacy_emails = _candidate_legacy_emails(norm_channel, ext_id)
        existing_customer = Customer.query.filter(Customer.email.in_(legacy_emails)).first()
        display_name = _default_display_name(norm_channel, ext_id, incoming.metadata)

        if existing_customer:
            identity = cls._create_identity_safe(
                customer_id=existing_customer.id,
                channel=norm_channel,
                channel_account_id=account,
                external_user_id=ext_id,
                display_name=existing_customer.name or display_name,
            )
            return existing_customer, identity

        try:
            customer = Customer(name=display_name, email=primary_email)
            db.session.add(customer)
            db.session.flush()
            identity = CustomerChannelIdentity(
                customer_id=customer.id,
                channel=norm_channel,
                channel_account_id=account,
                external_user_id=ext_id,
                display_name=display_name,
                is_verified=False,
                identity_metadata={},
            )
            db.session.add(identity)
            db.session.commit()
            return customer, identity
        except IntegrityError:
            db.session.rollback()
            identity = cls.find_identity(norm_channel, ext_id, account)
            if identity and identity.customer:
                return identity.customer, identity
            customer = Customer.query.filter_by(email=primary_email).first()
            if customer:
                identity = cls._create_identity_safe(
                    customer_id=customer.id,
                    channel=norm_channel,
                    channel_account_id=account,
                    external_user_id=ext_id,
                    display_name=customer.name,
                )
                return customer, identity
            raise

    @classmethod
    def _create_identity_safe(
        cls,
        *,
        customer_id: int,
        channel: str,
        channel_account_id: str,
        external_user_id: str,
        display_name: str | None = None,
    ) -> CustomerChannelIdentity:
        try:
            identity = CustomerChannelIdentity(
                customer_id=customer_id,
                channel=channel,
                channel_account_id=channel_account_id,
                external_user_id=external_user_id,
                display_name=display_name,
                is_verified=False,
            )
            db.session.add(identity)
            db.session.commit()
            return identity
        except IntegrityError:
            db.session.rollback()
            found = cls.find_identity(channel, external_user_id, channel_account_id)
            if found:
                return found
            raise

    @classmethod
    def link_identity(
        cls,
        *,
        customer_id: int,
        channel: str,
        external_user_id: str,
        channel_account_id: str = "",
        display_name: str | None = None,
        verified: bool = True,
        force_reassign: bool = False,
        metadata: dict | None = None,
    ) -> CustomerChannelIdentity:
        """Explicitly associate a verified channel identity with an existing internal Customer."""
        customer = db.session.get(Customer, customer_id)
        if not customer:
            raise CustomerNotFoundError(f"Customer {customer_id} not found.")

        norm_channel = normalize_channel_name(channel)
        account = (channel_account_id or "").strip()
        ext_id = external_user_id.strip()
        if not ext_id:
            raise ValueError("external_user_id is required.")

        existing = CustomerChannelIdentity.query.filter_by(
            channel=norm_channel,
            channel_account_id=account,
            external_user_id=ext_id,
        ).first()

        if existing:
            if existing.customer_id != customer_id:
                if not force_reassign:
                    raise IdentityConflictError(
                        f"Identity {norm_channel}:{ext_id} is already linked to customer {existing.customer_id}."
                    )
                existing.customer_id = customer_id
            if verified:
                existing.is_verified = True
            if display_name:
                existing.display_name = display_name
            if metadata:
                merged_meta = dict(existing.identity_metadata or {})
                merged_meta.update(metadata)
                existing.identity_metadata = merged_meta
            db.session.commit()
            return existing

        identity = CustomerChannelIdentity(
            customer_id=customer.id,
            channel=norm_channel,
            channel_account_id=account,
            external_user_id=ext_id,
            display_name=display_name or customer.name,
            is_verified=verified,
            identity_metadata=metadata or {},
        )
        db.session.add(identity)
        db.session.commit()
        return identity

    @staticmethod
    def list_identities(customer_id: int) -> list[CustomerChannelIdentity]:
        return (
            CustomerChannelIdentity.query
            .filter_by(customer_id=customer_id)
            .order_by(CustomerChannelIdentity.created_at.asc())
            .all()
        )

    @staticmethod
    def merge_customers(*, source_customer_id: int, target_customer_id: int) -> Customer:
        """Explicitly consolidate a duplicate customer record into a verified target customer."""
        if source_customer_id == target_customer_id:
            raise ValueError("Source and target customer IDs must differ.")

        source = db.session.get(Customer, source_customer_id)
        target = db.session.get(Customer, target_customer_id)
        if not source or not target:
            raise CustomerNotFoundError("Both source and target customers must exist.")

        try:
            CustomerChannelIdentity.query.filter_by(customer_id=source.id).update({"customer_id": target.id})
            Conversation.query.filter_by(customer_id=source.id).update({"customer_id": target.id})
            Message.query.filter_by(customer_id=source.id).update({"customer_id": target.id})
            Order.query.filter_by(customer_id=source.id).update({"customer_id": target.id})
            MediaFile.query.filter_by(customer_id=source.id).update({"customer_id": target.id})
            db.session.flush()
            # Expire ORM collections on source so cascade='delete-orphan' does not touch moved children
            db.session.expire(source)
            db.session.delete(source)
            db.session.commit()
            return target
        except Exception:
            db.session.rollback()
            raise
