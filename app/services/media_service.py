import base64
import logging
import mimetypes
import os
import uuid
from pathlib import Path

import requests
from werkzeug.utils import secure_filename

from app.config import Config
from app.extensions import db
from app.models import MediaFile

logger = logging.getLogger(__name__)

IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
AUDIO_MIME_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/ogg",
    "audio/webm", "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/flac",
}


class MediaService:
    @staticmethod
    def save_and_process(*, file_name, content, mime_type, media_type, customer_id, source):
        if not content:
            raise ValueError("Uploaded media is empty.")
        try:
            from flask import current_app
            max_img = current_app.config.get("MEDIA_MAX_IMAGE_MB", Config.MEDIA_MAX_IMAGE_MB)
            max_aud = current_app.config.get("MEDIA_MAX_AUDIO_MB", Config.MEDIA_MAX_AUDIO_MB)
        except Exception:
            max_img, max_aud = Config.MEDIA_MAX_IMAGE_MB, Config.MEDIA_MAX_AUDIO_MB

        if media_type == "image":
            allowed, max_mb = IMAGE_MIME_TYPES, max_img
        elif media_type == "audio":
            allowed, max_mb = AUDIO_MIME_TYPES, max_aud
        else:
            raise ValueError("Unsupported media type.")
        mime_type = (mime_type or mimetypes.guess_type(file_name)[0] or "").lower().split(";", 1)[0].strip()
        if mime_type not in allowed:
            raise ValueError(f"Unsupported {media_type} format: {mime_type or 'unknown'}")
        if len(content) > max_mb * 1024 * 1024:
            raise ValueError(f"{media_type.title()} exceeds the {max_mb} MB limit.")

        safe_name = secure_filename(file_name) or f"upload{mimetypes.guess_extension(mime_type) or ''}"
        extension = Path(safe_name).suffix.lower().lstrip(".") or (mimetypes.guess_extension(mime_type) or "bin").lstrip(".")
        file_path = f"db://media_files/{uuid.uuid4().hex}/{safe_name}"
        record = MediaFile(
            file_name=safe_name[:255], extension=extension[:20], file_path=file_path,
            content=content, media_type=media_type, mime_type=mime_type,
            source=source, customer_id=customer_id,
        )
        db.session.add(record)
        db.session.commit()  # Preserve the original bytes even if AI processing is temporarily unavailable.

        processed_text = None
        try:
            if media_type == "image":
                processed_text = MediaService.describe_image(content, mime_type)
            else:
                processed_text = MediaService.transcribe_audio(content, safe_name, mime_type)
        except Exception as exc:
            logger.warning("AI processing failed for %s media_file_id=%s: %s", media_type, record.id, exc)
            processed_text = None

        return record, processed_text

    @staticmethod
    def describe_image(content, mime_type):
        if not Config.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is required for image understanding.")
        encoded = base64.b64encode(content).decode("ascii")
        data_url = f"data:{mime_type};base64,{encoded}"
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": Config.GROQ_VISION_MODEL,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": "Describe this image for a customer-service assistant. Extract visible product names, labels, model numbers, and relevant details. Do not guess details that are not visible."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ]}],
                }, timeout=90,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            err_body = exc.response.text if exc.response is not None else str(exc)
            raise RuntimeError(f"Groq Vision API error ({status}): {err_body}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Groq Vision API request failed: {exc}") from exc

    @staticmethod
    def transcribe_audio(content, file_name, mime_type):
        if not Config.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is required for audio transcription.")
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
                data={"model": Config.GROQ_STT_MODEL, "response_format": "json"},
                files={"file": (file_name, content, mime_type)}, timeout=180,
            )
            response.raise_for_status()
            return (response.json().get("text") or "").strip()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            err_body = exc.response.text if exc.response is not None else str(exc)
            raise RuntimeError(f"Groq Audio Transcription API error ({status}): {err_body}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Groq Audio Transcription API request failed: {exc}") from exc
