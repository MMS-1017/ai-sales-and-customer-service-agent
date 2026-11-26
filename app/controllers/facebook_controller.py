from flask import Blueprint, request

from app.channels.dispatcher import handle_channel_request
from app.channels.messenger_adapter import MessengerAdapter
from app.schemas import ChannelType
from app.services.channel_service import WebhookDeduplicator

webhook_deduplicator = WebhookDeduplicator()

facebook_bp = Blueprint(
    "facebook",
    __name__,
)


@facebook_bp.get("/webhooks/facebook")
def verify_facebook_webhook():
    adapter = MessengerAdapter()
    return adapter.verify_subscription_challenge(request)


@facebook_bp.post("/webhooks/facebook")
def facebook_webhook():
    return handle_channel_request(
        ChannelType.MESSENGER.value,
        request,
        deduplicator=webhook_deduplicator,
    )
