import base64    # To Convert binary files to be JSON friendly
import io
import logging
import mimetypes
import os
import uuid       # To generate a random unique Identifier. Why? because if two users uploaded same file name, we don't want to overwrite the previous one. 
from pathlib import Path

import requests
from werkzeug.utils import secure_filename  # To clean filename

from app.config import Config
from app.extensions import db
from app.models import MediaFile

from flask import current_app

logger = logging.getLogger(__name__)

# Valid Types

IMAGE_MIME_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif", "image/bmp",
}

AUDIO_MIME_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/mp4", "audio/wav", "audio/x-wav", "audio/wave",
    "audio/ogg", "audio/x-ogg", "audio/opus", "audio/webm",
    "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/aac", "audio/x-aac",
    "audio/flac", "audio/x-flac", "audio/amr", "audio/3gpp",
    "video/mp4", "video/3gpp", "video/quicktime",
}


class MediaService:

    @staticmethod
    def get_storage_path(safe_name: str, media_type: str = "") -> Path:
        """Determines the local filesystem path to store the media file bytes."""
        try:
            base_dir = Path(current_app.config.get("MEDIA_STORAGE_DIR", Config.MEDIA_STORAGE_DIR))
        except Exception:
            base_dir = Path(Config.MEDIA_STORAGE_DIR)

        # Store in subdirectories by media type: 'images' or 'audios'
        sub_folder = f"{media_type}s" if media_type else "others"
        storage_dir = base_dir / sub_folder
        storage_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        return storage_dir / unique_name

    @staticmethod
    def save_and_process(*, file_name, content, mime_type, media_type, customer_id, source): # * to force passing arguments by its names

        if not content: # Binary Content
            raise ValueError("Uploaded media is empty.")
        
        # Ensure content is bytes
        if isinstance(content, str):
            content = content.encode("utf-8")
        elif not isinstance(content, (bytes, bytearray)):
            content = bytes(content)

        try:
            
            max_img = current_app.config.get("MEDIA_MAX_IMAGE_MB", Config.MEDIA_MAX_IMAGE_MB)
            max_aud = current_app.config.get("MEDIA_MAX_AUDIO_MB", Config.MEDIA_MAX_AUDIO_MB)

        except Exception:
            max_img, max_aud = Config.MEDIA_MAX_IMAGE_MB, Config.MEDIA_MAX_AUDIO_MB
        
        # We used try/except because current_app not always availlable

        if media_type == "image":
            allowed, max_mb = IMAGE_MIME_TYPES, max_img

        elif media_type == "audio":
            allowed, max_mb = AUDIO_MIME_TYPES, max_aud

        else:
            raise ValueError("Unsupported media type.")
        
        mime_type = (
            mime_type 
            or mimetypes.guess_type(file_name)[0] 
            or "").lower().split(";", 1)[0].strip()

        is_allowed = (
            mime_type in allowed
            or (media_type == "audio" and (mime_type.startswith("audio/") or mime_type in AUDIO_MIME_TYPES))
            or (media_type == "image" and (mime_type.startswith("image/") or mime_type in IMAGE_MIME_TYPES))
        )
        if not is_allowed:
            raise ValueError(f"Unsupported {media_type} format: {mime_type or 'unknown'}")
        
        if len(content) > max_mb * 1024 * 1024:
            raise ValueError(f"{media_type.title()} exceeds the {max_mb} MB limit.")

        raw_safe = secure_filename(file_name)
        safe_name = raw_safe or f"upload{mimetypes.guess_extension(mime_type) or ''}"

        extension = Path(safe_name).suffix.lower().lstrip(".") or (
            mimetypes.guess_extension(mime_type) or "bin"
            ).lstrip(".")

        # 1. Save locally in form of bytes
        local_path = MediaService.get_storage_path(safe_name, media_type)
        with open(local_path, "wb") as f:
            f.write(content)

        file_path_str = str(local_path.resolve())

        # 2. Record metadata and local path in DB
        record = MediaFile(
            file_name=safe_name[:255], 
            extension=extension[:20], 
            file_path=file_path_str,
            content=content, 
            media_type=media_type, 
            mime_type=mime_type,
            source=source, 
            customer_id=customer_id,
        )

        db.session.add(record)
        db.session.commit()  
        # Preserve the original bytes even if AI processing is temporarily unavailable.

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
                headers = {
                            "Authorization": f"Bearer {Config.GROQ_API_KEY}", 
                            "Content-Type": "application/json"
                        },
                json = {
                            "model": Config.GROQ_VISION_MODEL,
                            "temperature": 0,
                            "messages": [{
                                "role": "user", 
                                "content": [
                                {
                                    "type": "text", 
                                    "text": "Describe this image for a \
                                            customer-service assistant. Extract visible product names,\
                                            labels, model numbers, and relevant details. \
                                            Do not guess details that are not visible."},
                                {
                                    "type": "image_url", 
                                    "image_url": {"url": data_url}
                                },
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
        
        # Clean mime_type
        clean_mime = (mime_type or "").lower().split(";", 1)[0].strip()

        # When audio is received in an MP4/3GP container (e.g. from Meta Messenger voice notes),
        # normalize upload MIME to audio/mp4 so Whisper API strictly treats it as audio.
        upload_mime = "audio/mp4" if clean_mime in ("video/mp4", "video/3gpp") else (clean_mime or "audio/mp3")

        # Ensure filename has an allowed Whisper audio extension (mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg, flac)
        base, ext = os.path.splitext(file_name or "audio.mp4")
        if not ext or ext.lower() not in (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".flac"):
            if "mp4" in clean_mime:
                ext = ".mp4"
            elif "m4a" in clean_mime:
                ext = ".m4a"
            elif "ogg" in clean_mime or "opus" in clean_mime:
                ext = ".ogg"
            elif "wav" in clean_mime:
                ext = ".wav"
            elif "webm" in clean_mime:
                ext = ".webm"
            else:
                ext = ".mp4" if clean_mime in ("video/mp4", "audio/mp4") else ".mp3"
            file_name = f"{base or 'audio'}{ext}"

        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers = {
                    "Authorization": f"Bearer {Config.GROQ_API_KEY}"
                },
                data = {
                    "model": Config.GROQ_STT_MODEL,
                    "response_format": "json"
                },
                files ={
                    "file": (file_name, content, upload_mime)
                    }, 
                timeout=180
            )

            response.raise_for_status()
            return (response.json().get("text") or "").strip()
        
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            err_body = exc.response.text if exc.response is not None else str(exc)
            raise RuntimeError(f"Groq Audio Transcription API error ({status}): {err_body}") from exc
        
        except requests.RequestException as exc:
            raise RuntimeError(f"Groq Audio Transcription API request failed: {exc}") from exc

    @staticmethod
    def get_by_id(media_id: int):
        return db.session.get(MediaFile, media_id)

    @staticmethod
    def get_media_bytes(media_id: int) -> tuple[bytes | None, MediaFile | None]:
        """
        Retrieves the media file in its original raw bytes.
        Reads from local filesystem first; falls back to DB content if local file is missing.
        """
        media = MediaService.get_by_id(media_id)
        if not media:
            return None, None

        # 1. Try reading from local filesystem
        if media.file_path and os.path.exists(media.file_path):
            try:
                with open(media.file_path, "rb") as f:
                    return f.read(), media
            except OSError as exc:
                logger.warning("Failed to read local media file at %s: %s", media.file_path, exc)

        # 2. Fallback to database binary content
        if media.content:
            return bytes(media.content), media

        return None, media

    @staticmethod
    def get_original_file(media_id: int):
        """
        Retrieves the media file in its original form ready for transmission or download.
        Returns (io.BytesIO(data), mime_type, file_name, file_size) or None.
        """
        raw_bytes, media = MediaService.get_media_bytes(media_id)
        if not media or raw_bytes is None:
            return None

        stream = io.BytesIO(raw_bytes)
        mime_type = media.mime_type or "application/octet-stream"
        file_name = media.file_name or f"media_{media.id}.{media.extension}"
        return stream, mime_type, file_name, len(raw_bytes)

    @staticmethod
    def get_local_path(media_id: int) -> str | None:
        """Returns the local filesystem path if the media file exists locally."""
        media = MediaService.get_by_id(media_id)
        if media and media.file_path and os.path.exists(media.file_path):
            return media.file_path
        return None

    @staticmethod
    def list_by_customer(customer_id: int):
        return (
            MediaFile.query.filter_by(customer_id=customer_id)
            .order_by(MediaFile.created_at.desc())
            .all()
        )
