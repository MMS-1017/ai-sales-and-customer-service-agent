from flask import Blueprint, jsonify, request

from app.agent import agent_graph
from app.config import Config
from app.extensions import db
from app.models import Customer
from app.services.conversation_service import ConversationService
from app.services.facebook_service import FacebookService


facebook_bp = Blueprint(
    "facebook",
    __name__,
)


@facebook_bp.get("/webhooks/facebook")
def verify_facebook_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if (
        mode == "subscribe"
        and token == Config.FACEBOOK_VERIFY_TOKEN
    ):
        return challenge, 200

    return "Forbidden", 403


@facebook_bp.post("/webhooks/facebook")
def facebook_webhook():
    raw_body = request.get_data()

    signature = request.headers.get(
        "X-Hub-Signature-256"
    )

    if not FacebookService.verify_signature(
        raw_body,
        signature,
    ):
        return jsonify({
            "success": False,
            "error": "Invalid webhook signature.",
        }), 403

    data = request.get_json(silent=True) or {}

    if data.get("object") != "page":
        return jsonify({
            "success": False,
            "error": "Invalid webhook object.",
        }), 400

    for entry in data.get("entry", []):
        for messaging_event in entry.get(
            "messaging",
            [],
        ):
            process_message(messaging_event)

    return "EVENT_RECEIVED", 200


def process_message(event):
    sender = event.get("sender", {})
    sender_id = sender.get("id")

    message = event.get("message", {})
    text = message.get("text")

    if not sender_id or not text:
        return

    text = text.strip()

    if not text:
        return

    try:
        customer = get_or_create_facebook_customer(
            sender_id
        )

        conversation_id = (
            f"facebook:{sender_id}"
        )

        history = ConversationService.get_history(
            conversation_id
        )

        result = agent_graph.invoke({
            "messages": history + [text],
            "customer_id": customer.id,
        })

        response = result.get(
            "response",
            "Sorry, I couldn't process your request.",
        )

        ConversationService.add_message(
            conversation_id,
            text,
        )

        ConversationService.add_message(
            conversation_id,
            response,
        )

        FacebookService.send_message(
            sender_id,
            response,
        )

    except Exception as exc:
        print(f"Error processing Facebook message from {sender_id}: {exc}")


def get_or_create_facebook_customer(sender_id):
    email = f"facebook_{sender_id}@facebook.local"

    customer = Customer.query.filter_by(
        email=email
    ).first()

    if customer:
        return customer

    customer = Customer(
        name=f"Facebook User {sender_id}",
        email=email,
    )

    db.session.add(customer)
    db.session.commit()

    return customer