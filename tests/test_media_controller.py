import io
import pytest
from unittest.mock import patch
from app import create_app
from app.extensions import db
from app.models import Customer, MediaFile


@pytest.fixture
def sqlite_app():
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    with test_app.app_context():
        db.create_all()
        cust = Customer(name="Test Customer", email="media_test@example.com")
        db.session.add(cust)
        db.session.commit()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(sqlite_app):
    return sqlite_app.test_client()


def test_media_retrieval_image_success(client, sqlite_app):
    with sqlite_app.app_context():
        fake_png_bytes = b"\x89PNG\r\n\x1a\nfake_image_bytes"
        record = MediaFile(
            file_name="test_screenshot.png",
            extension="png",
            file_path="db://media_files/test_uuid/test_screenshot.png",
            content=fake_png_bytes,
            media_type="image",
            mime_type="image/png",
            source="web_chat",
            customer_id=1,
        )
        db.session.add(record)
        db.session.commit()
        media_id = record.id

    # Inline streaming retrieval (for browser <img> or viewing)
    response = client.get(f"/api/media/{media_id}")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("image/png")
    assert response.data == fake_png_bytes
    assert "attachment" not in response.headers.get("Content-Disposition", "")


def test_media_retrieval_audio_as_download(client, sqlite_app):
    with sqlite_app.app_context():
        fake_audio_bytes = b"OggSfake_voice_bytes"
        record = MediaFile(
            file_name="voice_note.ogg",
            extension="ogg",
            file_path="db://media_files/test_uuid_2/voice_note.ogg",
            content=fake_audio_bytes,
            media_type="audio",
            mime_type="audio/ogg",
            source="whatsapp",
            customer_id=1,
        )
        db.session.add(record)
        db.session.commit()
        media_id = record.id

    # Download mode (?download=1)
    response = client.get(f"/api/media/{media_id}?download=1")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("audio/ogg")
    assert response.data == fake_audio_bytes
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert "voice_note.ogg" in response.headers.get("Content-Disposition", "")


def test_media_retrieval_not_found(client, sqlite_app):
    response = client.get("/api/media/999999")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "not found" in data["error"].lower()


def test_media_info_endpoint(client, sqlite_app):
    with sqlite_app.app_context():
        fake_bytes = b"\xff\xd8\xff\xe0jpeg_sample"
        record = MediaFile(
            file_name="sample.jpg",
            extension="jpg",
            file_path="db://media_files/test_uuid_3/sample.jpg",
            content=fake_bytes,
            media_type="image",
            mime_type="image/jpeg",
            source="web_chat",
            customer_id=1,
        )
        db.session.add(record)
        db.session.commit()
        media_id = record.id

    response = client.get(f"/api/media/{media_id}/info")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    media_info = data["media"]
    assert media_info["id"] == media_id
    assert media_info["file_name"] == "sample.jpg"
    assert media_info["mime_type"] == "image/jpeg"
    assert media_info["media_type"] == "image"
    assert media_info["size_bytes"] == len(fake_bytes)
    assert media_info["url"] == f"/api/media/{media_id}"
    assert media_info["download_url"] == f"/api/media/{media_id}?download=1"


def test_list_media_by_customer(client, sqlite_app):
    with sqlite_app.app_context():
        rec1 = MediaFile(
            file_name="item1.jpg",
            extension="jpg",
            file_path="db://media_files/test_uuid_4/item1.jpg",
            content=b"bytes1",
            media_type="image",
            mime_type="image/jpeg",
            source="web_chat",
            customer_id=1,
        )
        db.session.add(rec1)
        db.session.commit()

    response = client.get("/api/media?customer_id=1")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] >= 1
    assert any(m["file_name"] == "item1.jpg" for m in data["media"])


def test_chat_upload_returns_media_url(client, sqlite_app):
    image_bytes = b"\xff\xd8\xff\xe0fake_jpeg"
    data = {
        "message": "Check this",
        "customer_id": 1,
        "conversation_id": "test_chat_return_media_id",
        "file": (io.BytesIO(image_bytes), "camera.jpg", "image/jpeg"),
    }

    with patch("app.services.media_service.MediaService.describe_image", return_value="A camera photo."), \
         patch("app.agent.agent_graph.invoke", return_value={"response": "I see the camera photo."}):
        response = client.post(
            "/api/chat",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result["success"] is True
        assert "media_id" in result
        assert result["media_url"] == f"/api/media/{result['media_id']}"

        # Verify retrieving that media URL returns the exact uploaded bytes!
        media_resp = client.get(result["media_url"])
        assert media_resp.status_code == 200
        assert media_resp.data == image_bytes
