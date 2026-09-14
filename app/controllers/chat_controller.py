from flask import Blueprint, jsonify, request, render_template

from app.agent import agent_graph

chat_bp = Blueprint("chat", __name__)


@chat_bp.get("/chat")
def chat_page():
    return render_template("chat.html")


@chat_bp.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get("message", "").strip()
    customer_id = data.get("customer_id", 1)

    if not message:
        return jsonify({
            "success": False,
            "error": "Message is required."
        }), 400

    try:
        result = agent_graph.invoke({
            "messages": [message],
            "customer_id": customer_id,
        })

        return jsonify({
            "success": True,
            "response": result.get("response"),
            "intent": result.get("intent"),
            "tool_result": result.get("tool_result"),
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500