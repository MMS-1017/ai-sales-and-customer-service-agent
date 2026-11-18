import pytest
from unittest.mock import patch, MagicMock
from app.controllers.whatsapp_controller import webhook_deduplicator


@pytest.fixture(autouse=True)
def clean_deduplicator():
    webhook_deduplicator.clear()
    yield
    webhook_deduplicator.clear()


def test_whatsapp_webhook_unauthorized_secret(client, app):
    app.config["WAHA_WEBHOOK_SECRET"] = "expected_secret_123"
    response = client.post(
        "/webhooks/whatsapp",
        json={"event": "message", "payload": {"from": "1234567890@c.us", "body": "Hello"}},
        headers={"X-Webhook-Secret": "wrong_secret"},
    )
    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized webhook"


def test_whatsapp_webhook_ignores_from_me(client, app):
    app.config["WAHA_WEBHOOK_SECRET"] = ""
    response = client.post(
        "/webhooks/whatsapp",
        json={"event": "message", "payload": {"fromMe": True, "from": "1234567890@c.us", "body": "Hello"}},
    )
    assert response.status_code == 200
    assert response.get_json() == {"status": "ignored", "reason": "outgoing_message"}


def test_whatsapp_webhook_ignores_group_message(client, app):
    app.config["WAHA_WEBHOOK_SECRET"] = ""
    response = client.post(
        "/webhooks/whatsapp",
        json={"event": "message", "payload": {"from": "1234567890@g.us", "body": "Group message"}},
    )
    assert response.status_code == 200
    assert response.get_json() == {"status": "ignored", "reason": "missing_chat_or_group"}


def test_whatsapp_duplicate_webhook_protection(client, app, mock_llm):
    app.config["WAHA_WEBHOOK_SECRET"] = ""

    payload = {
        "event": "message",
        "payload": {
            "id": "wamid_unique_test_12345",
            "from": "966500000001@c.us",
            "body": "How much is Samsung Galaxy S24?",
        },
    }

    with patch("app.services.waha_service.WahaService.send_text") as mock_send:
        # First delivery: processed
        res1 = client.post("/webhooks/whatsapp", json=payload)
        assert res1.status_code == 200
        assert res1.get_json() == {"status": "processed"}
        assert mock_send.call_count == 1

        # Second delivery (duplicate retry): must be ignored, NOT re-processed!
        res2 = client.post("/webhooks/whatsapp", json=payload)
        assert res2.status_code == 200
        assert res2.get_json() == {"status": "ignored", "reason": "duplicate_message"}
        # send_text should still only have been called once
        assert mock_send.call_count == 1


def test_whatsapp_media_download_failure_does_not_crash_webhook(client, app, mock_llm):
    app.config["WAHA_WEBHOOK_SECRET"] = ""

    payload = {
        "event": "message",
        "payload": {
            "id": "wamid_media_fail_test",
            "from": "966500000002@c.us",
            "type": "image",
            "body": "Check this phone please",
            "media": {"url": "http://invalid-media-url.local/image.jpg", "mimetype": "image/jpeg"},
        },
    }

    with patch("app.services.waha_service.WahaService.download_media", side_effect=RuntimeError("WAHA media server offline")):
        with patch("app.services.waha_service.WahaService.send_text") as mock_send:
            response = client.post("/webhooks/whatsapp", json=payload)
            # Must NOT crash with 500
            assert response.status_code == 200
            assert response.get_json() == {"status": "processed"}
            assert mock_send.call_count == 1


def test_whatsapp_media_ai_failure_does_not_crash_webhook(client, app, mock_llm):
    app.config["WAHA_WEBHOOK_SECRET"] = ""

    payload = {
        "event": "message",
        "payload": {
            "id": "wamid_ai_fail_test",
            "from": "966500000003@c.us",
            "type": "image",
            "body": "Is this in stock?",
            "media": {"url": "http://media.local/image.jpg", "mimetype": "image/jpeg"},
        },
    }

    with patch("app.services.waha_service.WahaService.download_media", return_value=(b"fake_image_bytes", "image/jpeg", "image.jpg")):
        with patch("app.services.media_service.MediaService.describe_image", side_effect=RuntimeError("Groq Vision API rate limit")):
            with patch("app.services.waha_service.WahaService.send_text") as mock_send:
                response = client.post("/webhooks/whatsapp", json=payload)
                assert response.status_code == 200
                assert response.get_json() == {"status": "processed"}
                assert mock_send.call_count == 1


def test_whatsapp_empty_message_ignored(client, app):
    app.config["WAHA_WEBHOOK_SECRET"] = ""
    payload = {
        "event": "message",
        "payload": {
            "id": "wamid_empty_test",
            "from": "966500000004@c.us",
            "body": "   ",
        },
    }
    response = client.post("/webhooks/whatsapp", json=payload)
    assert response.status_code == 200
    assert response.get_json() == {"status": "ignored", "reason": "empty_message"}
