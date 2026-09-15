from flask import Blueprint, jsonify, request, render_template

from app.agent import agent_graph
from app.services.conversation_service import ConversationService


chat_bp = Blueprint("chat", __name__)


@chat_bp.get("/chat")
def chat_page():
    return render_template("chat.html")


@chat_bp.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get("message", "").strip()
    customer_id = data.get("customer_id", 1)
    conversation_id = data.get("conversation_id", "default")

    if not message:
        return jsonify({
            "success": False,
            "error": "Message is required.",
        }), 400

    try:
        history = ConversationService.get_history(conversation_id)

        result = agent_graph.invoke({
            "messages": history + [message],
            "customer_id": customer_id,
        })

        response = result.get("response", "")

        ConversationService.add_message(conversation_id, message)
        ConversationService.add_message(conversation_id, response)

        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "response": response,
            "intent": result.get("intent"),
            "tool_result": result.get("tool_result"),
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500