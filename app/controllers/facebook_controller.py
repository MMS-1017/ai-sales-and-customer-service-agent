import mimetypes
import requests
from flask import Blueprint, jsonify, request

from app.agent import agent_graph
from app.config import Config
from app.extensions import db
from app.models import Customer
from app.services.conversation_service import ConversationService
from app.services.facebook_service import FacebookService
from app.services.media_service import MediaService


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
    text = (message.get("text") or "").strip()
    attachments = message.get("attachments") or []

    if not sender_id or (not text and not attachments):
        return

    try:
        customer = get_or_create_facebook_customer(sender_id)
        conversation_id = f"facebook:{sender_id}"
        history = ConversationService.get_history(conversation_id)

        # Process any media attachments (images, audio clips, or voice notes)
        media_context = []
        for att in attachments:
            att_type = att.get("type")  # "image", "audio", or "video"
            if att_type in ("image", "audio", "video"):
                media_url = (att.get("payload") or {}).get("url")
                if media_url:
                    try:
                        res = requests.get(media_url, timeout=30)
                        res.raise_for_status()
                        content = res.content
                        raw_mime = res.headers.get("Content-Type", "")
                        mime_type = raw_mime.split(";", 1)[0].strip().lower()
                        media_type = "audio" if att_type in ("audio", "video") else "image"

                        ext = mimetypes.guess_extension(mime_type)
                        if not ext:
                            if "mp4" in mime_type:
                                ext = ".mp4"
                            elif "ogg" in mime_type or "opus" in mime_type:
                                ext = ".ogg"
                            elif "wav" in mime_type:
                                ext = ".wav"
                            elif "webm" in mime_type:
                                ext = ".webm"
                            else:
                                ext = ".jpg" if media_type == "image" else ".mp4"

                        file_name = f"fb_{sender_id}_{media_type}{ext}"

                        record, processed_text = MediaService.save_and_process(
                            file_name=file_name,
                            content=content,
                            mime_type=mime_type,
                            media_type=media_type,
                            customer_id=customer.id,
                            source="facebook",
                        )
                        label = "Image analysis" if media_type == "image" else "Audio transcription"
                        if processed_text:
                            media_context.append(f"[{label}: {processed_text}]")
                        else:
                            media_context.append(f"[Customer sent a {att_type}]")
                    except Exception as err:
                        print(f"[FB MEDIA ERROR] Failed to download/process {att_type}: {err}")

        full_message = "\n".join(part for part in [text] + media_context if part).strip()
        if not full_message:
            return

        result = agent_graph.invoke({
            "messages": history + [full_message],
            "customer_id": customer.id,
        })

        response = result.get(
            "response",
            "Sorry, I couldn't process your request.",
        )

        ConversationService.add_message(conversation_id, full_message)
        ConversationService.add_message(conversation_id, response)

        FacebookService.send_message(
            sender_id,
            response,
        )

    except Exception as exc:
        import traceback
        print(f"[FB ERROR] Processing message from {sender_id}: {exc}")
        traceback.print_exc()
        # Print Facebook API response body if available
        if hasattr(exc, "response") and exc.response is not None:
            print(f"[FB API RESPONSE] Status: {exc.response.status_code}")
            print(f"[FB API RESPONSE] Body: {exc.response.text}")


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