from flask import Blueprint, render_template, request

from app.channels.dispatcher import handle_channel_request
from app.schemas import ChannelType

chat_bp = Blueprint("chat", __name__)


@chat_bp.get("/chat")
def chat_page():
    return render_template("chat.html")


@chat_bp.post("/api/chat")
def chat():
    return handle_channel_request(ChannelType.WEB_CHAT.value, request)
