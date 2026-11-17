from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.agent import agent_graph
from app.extensions import db
from app.models import Customer
from app.services.conversation_service import ConversationService
from app.services.waha_service import WahaService

import logging
logger = logging.getLogger(__name__)
whatsapp_bp = Blueprint("whatsapp", __name__)


@whatsapp_bp.post("/webhooks/whatsapp")
def whatsapp_webhook():
    """Receive WAHA `message` events and reply through the same agent graph."""
    # Optional shared-secret check. Configure the same value as a custom
    # webhook header in WAHA; when unset, this check is disabled for local dev.
    expected_secret = current_app.config.get("WAHA_WEBHOOK_SECRET")
    if expected_secret and request.headers.get("X-Webhook-Secret") != expected_secret:
        logger.warning("Unauthorized webhook received")
        return jsonify({"success": False, "error": "Unauthorized webhook"}), 401

    data = request.get_json(silent=True) or {}
    if data.get("event") != "message":
        logger.info("Unsupported event received")
        return jsonify({"status": "ignored", "reason": "unsupported_event"}), 200

    message = data.get("payload") or {}
    if message.get("fromMe"):
        logger.info("Outgoing message received")
        return jsonify({"status": "ignored", "reason": "outgoing_message"}), 200

    chat_id = message.get("from")
    text = (message.get("body") or "").strip()
    if not chat_id or not text:
        logger.info("Empty message received")
        return jsonify({"status": "ignored", "reason": "empty_message"}), 200

    # This demo handles direct chats only; do not create customers for groups.
    if "@g.us" in chat_id:
        logger.info("Group chat message received")
        return jsonify({"status": "ignored", "reason": "group_chat_not_supported"}), 200

    try:
        customer = get_or_create_whatsapp_customer(chat_id)
        conversation_id = f"whatsapp:{chat_id}"
        history = ConversationService.get_history(conversation_id)

        result = agent_graph.invoke({
            "messages": history + [text],
            "customer_id": customer.id,
        })
        response_text = (result.get("response") or "Sorry, I couldn't process your request.").strip()

        # Persist in-memory conversation history only after the agent succeeds.
        ConversationService.add_message(conversation_id, text)
        ConversationService.add_message(conversation_id, response_text)
        WahaService.send_text(chat_id, response_text)

        return jsonify({"status": "processed"}), 200
    except Exception:
        db.session.rollback()
        logger.exception("Failed to process WAHA message from %s", chat_id)
        # A 500 lets WAHA retry according to its webhook retry configuration.
        return jsonify({"success": False, "error": "Message processing failed"}), 500


def get_or_create_whatsapp_customer(chat_id: str) -> Customer:
    """Map a WhatsApp chat to a stable Customer using a synthetic unique email."""
    normalized = chat_id.split("@", 1)[0].replace("+", "")
    email = f"whatsapp_{normalized}@whatsapp.local"
    customer = Customer.query.filter_by(email=email).first()
    if customer:
        return customer

    customer = Customer(name=f"WhatsApp Customer {normalized}", email=email)
    db.session.add(customer)
    db.session.commit()
    return customer
