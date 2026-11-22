import io
import os
import shutil
import tempfile
import pytest

from app import create_app
from app.extensions import db
from app.models import Customer, MediaFile
from app.services.media_service import MediaService


@pytest.fixture
def app_with_media_storage():
    temp_dir = tempfile.mkdtemp()
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "MEDIA_STORAGE_DIR": temp_dir,
            "GROQ_API_KEY": None,  # Skip external API calls
        }
    )

    with app.app_context():
        db.create_all()
        customer = Customer(name="Media Tester", email="mediatester@example.com")
        db.session.add(customer)
        db.session.commit()

        yield app, customer.id, temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_save_image_locally_as_bytes(app_with_media_storage):
    app, customer_id, temp_dir = app_with_media_storage
    raw_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64 + b"IEND"

    with app.app_context():
        record, _ = MediaService.save_and_process(
            file_name="sample_photo.png",
            content=raw_image_bytes,
            mime_type="image/png",
            media_type="image",
            customer_id=customer_id,
            source="web_chat",
        )

        assert record.id is not None
        assert record.file_name == "sample_photo.png"
        assert record.media_type == "image"
        assert record.mime_type == "image/png"

        # 1. Verify file exists on local filesystem
        assert os.path.exists(record.file_path)
        assert temp_dir in record.file_path

        # 2. Verify bytes on local disk match original uploaded bytes exactly
        with open(record.file_path, "rb") as f:
            disk_bytes = f.read()
        assert disk_bytes == raw_image_bytes


def test_save_audio_locally_as_bytes(app_with_media_storage):
    app, customer_id, temp_dir = app_with_media_storage
    raw_audio_bytes = b"ID3\x03\x00\x00\x00" + b"\xff\xfb\x90\x00" * 32

    with app.app_context():
        record, _ = MediaService.save_and_process(
            file_name="voice_note.mp3",
            content=raw_audio_bytes,
            mime_type="audio/mpeg",
            media_type="audio",
            customer_id=customer_id,
            source="whatsapp",
        )

        assert record.id is not None
        assert record.media_type == "audio"
        assert os.path.exists(record.file_path)

        with open(record.file_path, "rb") as f:
            disk_bytes = f.read()
        assert disk_bytes == raw_audio_bytes


def test_retrieve_media_in_original_form(app_with_media_storage):
    app, customer_id, _ = app_with_media_storage
    raw_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"TESTIMAGE"

    with app.app_context():
        record, _ = MediaService.save_and_process(
            file_name="logo.png",
            content=raw_bytes,
            mime_type="image/png",
            media_type="image",
            customer_id=customer_id,
            source="web_chat",
        )

        # 1. Retrieve raw bytes via service
        retrieved_bytes, media = MediaService.get_media_bytes(record.id)
        assert retrieved_bytes == raw_bytes
        assert media.id == record.id

        # 2. Retrieve original file format stream via service
        stream, mime_type, file_name, file_size = MediaService.get_original_file(record.id)
        assert stream.read() == raw_bytes
        assert mime_type == "image/png"
        assert file_name == "logo.png"
        assert file_size == len(raw_bytes)


def test_media_api_endpoints_retrieve_original_form(app_with_media_storage):
    app, customer_id, _ = app_with_media_storage
    raw_bytes = b"\x89PNG\r\n\x1a\n" + b"\x12\x34\x56" * 20
    client = app.test_client()

    with app.app_context():
        record, _ = MediaService.save_and_process(
            file_name="invoice.png",
            content=raw_bytes,
            mime_type="image/png",
            media_type="image",
            customer_id=customer_id,
            source="web_chat",
        )
        media_id = record.id

    # 1. GET /api/media/<id> returns original bytes with original MIME type
    res = client.get(f"/api/media/{media_id}")
    assert res.status_code == 200
    assert res.data == raw_bytes
    assert "image/png" in res.headers.get("Content-Type", "")

    # 2. GET /api/media/<id>?download=1 returns as downloadable attachment
    download_res = client.get(f"/api/media/{media_id}?download=1")
    assert download_res.status_code == 200
    assert download_res.data == raw_bytes
    disposition = download_res.headers.get("Content-Disposition", "")
    assert "attachment" in disposition
    assert "invoice.png" in disposition

    # 3. GET /api/media/<id>/raw returns application/octet-stream
    raw_res = client.get(f"/api/media/{media_id}/raw")
    assert raw_res.status_code == 200
    assert raw_res.data == raw_bytes
    assert "application/octet-stream" in raw_res.headers.get("Content-Type", "")

    # 4. GET /api/media/<id>/info confirms local storage & metadata
    info_res = client.get(f"/api/media/{media_id}/info")
    assert info_res.status_code == 200
    info_data = info_res.get_json()["media"]
    assert info_data["exists_locally"] is True
    assert info_data["size_bytes"] == len(raw_bytes)
    assert info_data["file_name"] == "invoice.png"
    assert info_data["url"] == f"/api/media/{media_id}"
