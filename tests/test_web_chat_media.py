import io
import pytest
from unittest.mock import patch


def test_chat_text_only_success(client, app, mock_llm):
    response = client.post(
        "/api/chat",
        json={"message": "What is the price of Samsung Galaxy S24?", "conversation_id": "test_chat_1"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "response" in data


def test_chat_invalid_mime_type_returns_400(client, app):
    data = {
        "message": "Here is a document",
        "file": (io.BytesIO(b"dummy pdf content"), "document.pdf", "application/pdf"),
    }
    response = client.post(
        "/api/chat",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "Only image and audio uploads are supported" in response.get_json()["error"]


def test_chat_unsupported_image_format_returns_400(client, app):
    data = {
        "message": "Here is a tiff",
        "file": (io.BytesIO(b"dummy tiff content"), "photo.tiff", "image/tiff"),
    }
    response = client.post(
        "/api/chat",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "Unsupported image format" in response.get_json()["error"]


def test_chat_oversized_file_returns_400(client, app, mock_llm):
    # Set limit to 1 MB for test
    app.config["MEDIA_MAX_IMAGE_MB"] = 1
    oversized_data = b"x" * (2 * 1024 * 1024)
    data = {
        "message": "Big image",
        "file": (io.BytesIO(oversized_data), "large.jpg", "image/jpeg"),
    }
    response = client.post(
        "/api/chat",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "exceeds" in response.get_json()["error"].lower()


def test_chat_valid_image_upload_with_vision(client, app, mock_llm):
    image_bytes = b"\xff\xd8\xff\xe0fake_jpeg_content"
    data = {
        "message": "Do you have this phone in stock?",
        "customer_id": 1,
        "conversation_id": "test_chat_image",
        "file": (io.BytesIO(image_bytes), "samsung.jpg", "image/jpeg"),
    }

    with patch("app.services.media_service.MediaService.describe_image", return_value="The image shows a Samsung Galaxy S24."):
        response = client.post(
            "/api/chat",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert "response" in result


def test_chat_valid_audio_upload_with_whisper(client, app, mock_llm):
    audio_bytes = b"OggSfake_ogg_audio_content"
    data = {
        "message": "",
        "customer_id": 1,
        "conversation_id": "test_chat_audio",
        "file": (io.BytesIO(audio_bytes), "voice.ogg", "audio/ogg"),
    }

    with patch("app.services.media_service.MediaService.transcribe_audio", return_value="I want to buy Samsung Galaxy S24"):
        response = client.post(
            "/api/chat",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert "response" in result


def test_chat_media_processing_failure_falls_back_gracefully(client, app, mock_llm):
    image_bytes = b"\xff\xd8\xff\xe0fake_jpeg"
    data = {
        "message": "Can you check this?",
        "customer_id": 1,
        "conversation_id": "test_chat_fallback",
        "file": (io.BytesIO(image_bytes), "phone.jpg", "image/jpeg"),
    }

    # Vision fails with API outage
    with patch("app.services.media_service.MediaService.describe_image", side_effect=RuntimeError("Groq Vision API timeout")):
        response = client.post(
            "/api/chat",
            data=data,
            content_type="multipart/form-data",
        )
        # Web chat must not crash with 500
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True


def test_chat_invalid_customer_id_returns_400(client, app):
    response = client.post(
        "/api/chat",
        json={"message": "Hello", "customer_id": "not_an_int"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid customer ID."

