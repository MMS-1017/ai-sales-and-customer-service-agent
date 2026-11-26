from flask import Blueprint, jsonify, render_template, request

from app.channels.dispatcher import handle_channel_request
from app.models import Conversation, Message
from app.schemas import ChannelType

chat_bp = Blueprint("chat", __name__)


@chat_bp.get("/chat")
def chat_page():
    return render_template("chat.html")


@chat_bp.post("/api/chat")
def chat():
    return handle_channel_request(ChannelType.WEB_CHAT.value, request)


@chat_bp.get("/api/chat/messages")
def poll_web_chat_messages():
    """Return live admin replies for an active Website Chat conversation."""
    conversation_id = (request.args.get("conversation_id") or "").strip()
    if not conversation_id:
        return jsonify({"success": True, "response_mode": "agent", "messages": []})

    try:
        after_id = int(request.args.get("after_id") or 0)
    except ValueError:
        after_id = 0

    conv = Conversation.query.filter_by(
        channel=ChannelType.WEB_CHAT.value,
        external_conversation_id=conversation_id,
    ).first()
    if not conv:
        return jsonify({"success": True, "response_mode": "agent", "messages": []})

    admin_messages = (
        Message.query
        .filter(
            Message.conversation_id == conv.id,
            Message.role == "admin",
            Message.id > after_id,
        )
        .order_by(Message.id.asc())
        .all()
    )
    return jsonify(
        {
            "success": True,
            "response_mode": conv.response_mode or "agent",
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in admin_messages
            ],
        }
    )
