from flask import Blueprint, jsonify, request, render_template
from werkzeug.utils import secure_filename

from app.agent import agent_graph
from app.extensions import db
from app.models import Customer
from app.services.conversation_service import ConversationService
from app.services.media_service import MediaService

chat_bp = Blueprint("chat", __name__)


@chat_bp.get("/chat")
def chat_page():
    return render_template("chat.html")


@chat_bp.post("/api/chat")
def chat():
    is_multipart = request.mimetype == "multipart/form-data"
    data = request.form if is_multipart else (request.get_json(silent=True) or {})
    message = (data.get("message") or "").strip()
    customer_id = data.get("customer_id", 1)
    conversation_id = data.get("conversation_id", "default")
    upload = request.files.get("file") if is_multipart else None

    if not message and not (upload and upload.filename):
        return jsonify({"success": False, "error": "Message or media file is required."}), 400

    try:
        try:
            customer_id_int = int(customer_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid customer ID."}), 400

        customer = db.session.get(Customer, customer_id_int)
        if not customer:
            return jsonify({"success": False, "error": "Customer not found."}), 404

        record = None
        if upload and upload.filename:
            file_name = secure_filename(upload.filename)
            content = upload.read()
            raw_mime = upload.mimetype or ""
            mime_type = raw_mime.split(";", 1)[0].strip().lower()
            if mime_type.startswith("image/"):
                media_type = "image"
            elif (
                mime_type.startswith("audio/")
                or mime_type in ("video/mp4", "video/3gpp", "video/quicktime")
                or file_name.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".mp4", ".aac"))
            ):
                media_type = "audio"
            else:
                media_type = None

            if not media_type:
                return jsonify({"success": False, "error": "Only image and audio uploads are supported."}), 400
            try:
                record, processed_text = MediaService.save_and_process(
                    file_name=file_name, content=content, mime_type=mime_type,
                    media_type=media_type, customer_id=customer.id, source="web_chat",
                )
            except ValueError as val_err:
                return jsonify({"success": False, "error": str(val_err)}), 400
            label = "Image analysis" if media_type == "image" else "Audio transcription"
            message = "\n".join(x for x in [message, f"[{label}: {processed_text}]" if processed_text else ""] if x)
            if not message:
                message = f"The customer uploaded a {media_type}."

        history = ConversationService.get_history(conversation_id)
        result = agent_graph.invoke({"messages": history + [message], "customer_id": customer.id})
        response = result.get("response", "")
        ConversationService.add_message(conversation_id, message)
        ConversationService.add_message(conversation_id, response)
        payload = {
            "success": True,
            "conversation_id": conversation_id,
            "response": response,
            "intent": result.get("intent"),
            "tool_result": result.get("tool_result"),
        }
        if record:
            payload["media_id"] = record.id
            payload["media_url"] = f"/api/media/{record.id}"
            payload["media_type"] = record.media_type
            payload["media_name"] = record.file_name
            payload["download_url"] = f"/api/media/{record.id}?download=1"
            payload["raw_url"] = f"/api/media/{record.id}/raw"
        return jsonify(payload)
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500
