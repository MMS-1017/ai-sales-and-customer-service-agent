from flask import Blueprint, request

from app.channels.dispatcher import handle_channel_request
from app.channels.whatsapp_adapter import (  # Re-exported for compatibility
    normalize_whatsapp_jid as _normalize_jid,
    resolve_whatsapp_chat_id as _resolve_whatsapp_chat_id,
)
from app.schemas import ChannelType
from app.services.channel_service import WebhookDeduplicator

whatsapp_bp = Blueprint("whatsapp", __name__)
webhook_deduplicator = WebhookDeduplicator()


@whatsapp_bp.post("/webhooks/whatsapp")
@whatsapp_bp.post("/webhooks/whatsapp/")
def whatsapp_webhook():
    return handle_channel_request(
        ChannelType.WHATSAPP.value,
        request,
        deduplicator=webhook_deduplicator,
    )
