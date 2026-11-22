import io
import os
from flask import Blueprint, jsonify, request, send_file
from app.models import MediaFile
from app.services.media_service import MediaService

media_bp = Blueprint("media", __name__, url_prefix="/api/media")


@media_bp.get("/<int:media_id>")
def get_media_file(media_id: int):
    """
    Retrieve the media file in its original form.
    - Inline view: /api/media/<id> (original mime_type)
    - Download original: /api/media/<id>?download=1
    """
    result = MediaService.get_original_file(media_id)
    if not result:
        return jsonify({"success": False, "error": "Media file not found or empty."}), 404

    stream, mime_type, download_name, _ = result
    as_attachment = request.args.get("download", "").lower() in ("1", "true", "yes")

    return send_file(
        stream,
        mimetype=mime_type,
        as_attachment=as_attachment,
        download_name=download_name,
    )


@media_bp.get("/<int:media_id>/raw")
def get_media_raw_bytes(media_id: int):
    """Retrieve the media file strictly as raw bytes (application/octet-stream)."""
    raw_bytes, media = MediaService.get_media_bytes(media_id)
    if not media or raw_bytes is None:
        return jsonify({"success": False, "error": "Media file not found or empty."}), 404

    return send_file(
        io.BytesIO(raw_bytes),
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=media.file_name or f"media_{media.id}.bin",
    )


@media_bp.get("/<int:media_id>/info")
def get_media_info(media_id: int):
    media = MediaService.get_by_id(media_id)
    if not media:
        return jsonify({"success": False, "error": "Media file not found."}), 404

    exists_locally = bool(media.file_path and os.path.exists(media.file_path))
    size_bytes = os.path.getsize(media.file_path) if exists_locally else (len(media.content) if media.content else 0)

    return jsonify({
        "success": True,
        "media": {
            "id": media.id,
            "file_name": media.file_name,
            "extension": media.extension,
            "media_type": media.media_type,
            "mime_type": media.mime_type,
            "file_path": media.file_path,
            "exists_locally": exists_locally,
            "size_bytes": size_bytes,
            "source": media.source,
            "customer_id": media.customer_id,
            "created_at": media.created_at.isoformat() if media.created_at else None,
            "url": f"/api/media/{media.id}",
            "raw_url": f"/api/media/{media.id}/raw",
            "download_url": f"/api/media/{media.id}?download=1",
        }
    })


@media_bp.get("")
def list_media():
    customer_id = request.args.get("customer_id")
    if customer_id:
        try:
            cid = int(customer_id)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid customer_id parameter."}), 400
        records = MediaService.list_by_customer(cid)
    else:
        records = MediaFile.query.order_by(MediaFile.created_at.desc()).limit(50).all()

    items = []
    for m in records:
        exists_locally = bool(m.file_path and os.path.exists(m.file_path))
        size_bytes = os.path.getsize(m.file_path) if exists_locally else (len(m.content) if m.content else 0)
        items.append({
            "id": m.id,
            "file_name": m.file_name,
            "extension": m.extension,
            "media_type": m.media_type,
            "mime_type": m.mime_type,
            "file_path": m.file_path,
            "exists_locally": exists_locally,
            "size_bytes": size_bytes,
            "source": m.source,
            "customer_id": m.customer_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "url": f"/api/media/{m.id}",
            "raw_url": f"/api/media/{m.id}/raw",
            "download_url": f"/api/media/{m.id}?download=1",
        })

    return jsonify({"success": True, "count": len(items), "media": items})
