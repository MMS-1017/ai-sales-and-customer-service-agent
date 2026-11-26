import hashlib
import hmac
import io
import json
from unittest.mock import patch

import pytest

from app import create_app
from app.channels import ChannelValidationError, MessengerAdapter, WebChatAdapter, WhatsAppAdapter
from app.controllers.facebook_controller import webhook_deduplicator as fb_dedup
from app.controllers.whatsapp_controller import webhook_deduplicator as wa_dedup
from app.extensions import db
from app.models import Customer
from app.schemas import (
    ChannelType,
    MediaType,
    MessageType,
    UnifiedAgentResponse,
    UnifiedIncomingMessage,
    UnifiedMediaRecord,
)
from app.services.conversation_service import ConversationService


@pytest.fixture
def sqlite_app():
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WAHA_WEBHOOK_SECRET": "",
            "FACEBOOK_APP_SECRET": "test_fb_secret",
        }
    )
    with test_app.app_context():
        db.create_all()
        cust = Customer(name="Web User", email="web@example.com")
        db.session.add(cust)
        db.session.commit()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sqlite_client(sqlite_app):
    wa_dedup.clear()
    fb_dedup.clear()
    ConversationService.clear()
    return sqlite_app.test_client()


def test_channel_type_aliases():
    assert ChannelType("whatsapp") == ChannelType.WHATSAPP
    assert ChannelType("wa") == ChannelType.WHATSAPP
    assert ChannelType("facebook") == ChannelType.MESSENGER
    assert ChannelType("messenger") == ChannelType.MESSENGER
    assert ChannelType("web_chat") == ChannelType.WEB_CHAT
    assert ChannelType("web") == ChannelType.WEB_CHAT


def test_unified_incoming_from_web_chat_and_validation():
    adapter = WebChatAdapter()
    msgs, ignore_reason = adapter.parse_payload_dict(
        {"message": "  Hello world  ", "customer_id": "1", "conversation_id": "conv_1"}
    )
    assert ignore_reason is None
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.channel == ChannelType.WEB_CHAT.value
    assert msg.external_user_id == "customer:1"
    assert msg.customer_id == 1
    assert msg.conversation_id == "conv_1"
    assert msg.text == "Hello world"
    assert msg.message_type == MessageType.TEXT
    assert msg.has_content is True

    with pytest.raises(ChannelValidationError, match="Invalid customer ID"):
        adapter.parse_payload_dict({"message": "Hi", "customer_id": "abc"})


def test_unified_incoming_from_whatsapp():
    adapter = WhatsAppAdapter()
    payload = {
        "event": "message",
        "session": "default",
        "payload": {
            "id": "false_201005087829@c.us_ABC123",
            "from": "201005087829@c.us",
            "body": "  Price?  ",
            "type": "ptt",
            "timestamp": 1764000000,
            "media": {"mimetype": "audio/ogg; codecs=opus", "url": "http://waha/audio.ogg"},
        },
    }
    msgs, ignore_reason = adapter.parse_payload_dict(payload)
    assert ignore_reason is None
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.channel == ChannelType.WHATSAPP.value
    assert msg.channel_account_id == "default"
    assert msg.external_user_id == "201005087829@c.us"
    assert msg.conversation_id == "whatsapp:201005087829@c.us"
    assert msg.external_message_id == "false_201005087829@c.us_ABC123"
    assert msg.text == "Price?"
    assert msg.message_type == MessageType.MIXED
    assert len(msg.attachments) == 1
    assert msg.attachments[0].media_type == MediaType.AUDIO
    assert msg.attachments[0].mime_type == "audio/ogg"


def test_unified_incoming_from_messenger():
    adapter = MessengerAdapter()
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_99",
                "messaging": [
                    {
                        "sender": {"id": "99887766"},
                        "timestamp": 1764000000000,
                        "message": {
                            "mid": "m_12345",
                            "text": "  Do you have headphones? ",
                            "attachments": [
                                {"type": "video", "payload": {"url": "https://cdn.fb/voice.mp4"}}
                            ],
                        },
                    }
                ],
            }
        ],
    }
    msgs, ignore_reason = adapter.parse_payload_dict(payload)
    assert ignore_reason is None
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.channel == ChannelType.MESSENGER.value
    assert msg.channel_account_id == "page_99"
    assert msg.external_user_id == "99887766"
    assert msg.conversation_id == "facebook:99887766"
    assert msg.external_message_id == "m_12345"
    assert msg.text == "Do you have headphones?"
    assert len(msg.attachments) == 1
    assert msg.attachments[0].media_type == MediaType.AUDIO
    assert msg.attachments[0].url == "https://cdn.fb/voice.mp4"


def test_unified_response_web_chat_serialization():
    resp = UnifiedAgentResponse(
        channel=ChannelType.WEB_CHAT.value,
        conversation_id="conv_1",
        customer_id=1,
        response="It costs $29.99",
        intent="product_details",
        media_records=[
            UnifiedMediaRecord(
                id=7,
                media_type=MediaType.IMAGE,
                file_name="earbuds.jpg",
                media_url="/api/media/7",
                download_url="/api/media/7?download=1",
                raw_url="/api/media/7/raw",
            )
        ],
    )
    data = resp.to_web_chat_dict()
    assert data["success"] is True
    assert data["response"] == "It costs $29.99"
    assert data["media_id"] == 7
    assert data["media_type"] == "image"
    assert data["media_name"] == "earbuds.jpg"


def test_all_three_channels_end_to_end_via_unified_pipeline(sqlite_client):
    mock_agent_result = {"response": "Unified reply", "intent": "general", "tool_result": None}

    with patch("app.services.channel_service.agent_graph.invoke", return_value=mock_agent_result) as mock_invoke:
        # 1. Web Chat
        web_res = sqlite_client.post(
            "/api/chat",
            json={"message": "Hello from web", "customer_id": 1, "conversation_id": "web_c1"},
        )
        assert web_res.status_code == 200
        assert web_res.get_json()["response"] == "Unified reply"

        # 2. WhatsApp
        with patch("app.services.waha_service.WahaService.send_text") as mock_wa_send:
            wa_res = sqlite_client.post(
                "/webhooks/whatsapp",
                json={
                    "event": "message",
                    "payload": {"id": "wa_1", "from": "201001112233@c.us", "body": "Hello from WA"},
                },
            )
            assert wa_res.status_code == 200
            assert wa_res.get_json() == {"status": "processed"}
            mock_wa_send.assert_called_once_with("201001112233@c.us", "Unified reply", reply_to="wa_1")

        # 3. Facebook Messenger
        fb_payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "fb_user_1"},
                            "message": {"mid": "mid_1", "text": "Hello from FB"},
                        }
                    ]
                }
            ],
        }
        raw_body = json.dumps(fb_payload).encode("utf-8")
        sig = "sha256=" + hmac.new(b"test_fb_secret", raw_body, hashlib.sha256).hexdigest()

        with patch("app.services.facebook_service.Config.FACEBOOK_APP_SECRET", "test_fb_secret"):
            with patch("app.services.facebook_service.FacebookService.send_message") as mock_fb_send:
                fb_res = sqlite_client.post(
                    "/webhooks/facebook",
                    data=raw_body,
                    content_type="application/json",
                    headers={"X-Hub-Signature-256": sig},
                )
                assert fb_res.status_code == 200
                mock_fb_send.assert_called_once_with("fb_user_1", "Unified reply")

        assert mock_invoke.call_count == 3


def test_web_chat_media_upload_through_unified_pipeline(sqlite_client):
    with patch("app.services.media_service.MediaService.describe_image", return_value="Blue earbuds"):
        with patch(
            "app.services.channel_service.agent_graph.invoke",
            return_value={"response": "Found Blue earbuds", "intent": "product_search", "tool_result": None},
        ):
            res = sqlite_client.post(
                "/api/chat",
                data={
                    "message": "What is this?",
                    "customer_id": "1",
                    "file": (io.BytesIO(b"\xff\xd8\xff\xe0img"), "buds.jpg", "image/jpeg"),
                },
                content_type="multipart/form-data",
            )
            assert res.status_code == 200
            body = res.get_json()
            assert body["success"] is True
            assert body["media_type"] == "image"
            assert body["media_id"] is not None


def test_channel_edge_cases_error_and_dedup_handling(sqlite_client):
    res_404 = sqlite_client.post(
        "/api/chat",
        json={"message": "Hello", "customer_id": 99999},
    )
    assert res_404.status_code == 404

    res_400 = sqlite_client.post("/api/chat", json={"message": "   "})
    assert res_400.status_code == 400

    res_bad_cust = sqlite_client.post("/api/chat", json={"message": "Hi", "customer_id": "abc"})
    assert res_bad_cust.status_code == 400
    assert res_bad_cust.get_json()["error"] == "Invalid customer ID."

    res_bad_mime = sqlite_client.post(
        "/api/chat",
        data={"message": "Doc", "file": (io.BytesIO(b"pdf"), "doc.pdf", "application/pdf")},
        content_type="multipart/form-data",
    )
    assert res_bad_mime.status_code == 400

    wa_empty = sqlite_client.post(
        "/webhooks/whatsapp",
        json={"event": "message", "payload": {"id": "wa_empty", "from": "201001112233@c.us", "body": "  "}},
    )
    assert wa_empty.status_code == 200
    assert wa_empty.get_json() == {"status": "ignored", "reason": "empty_message"}

    with patch("app.services.channel_service.agent_graph.invoke", return_value={"response": "Got it"}) as mock_invoke:
        with patch("app.services.waha_service.WahaService.download_media", side_effect=RuntimeError("offline")):
            with patch("app.services.waha_service.WahaService.send_text") as mock_send:
                payload = {
                    "event": "message",
                    "payload": {
                        "id": "wa_dup_1",
                        "from": "201001112233@c.us",
                        "type": "image",
                        "body": "Check image",
                        "media": {"mimetype": "image/jpeg"},
                    },
                }
                r1 = sqlite_client.post("/webhooks/whatsapp", json=payload)
                r2 = sqlite_client.post("/webhooks/whatsapp", json=payload)
                assert r1.status_code == 200
                assert r1.get_json() == {"status": "processed"}
                assert r2.status_code == 200
                assert r2.get_json() == {"status": "ignored", "reason": "duplicate_message"}
                assert mock_send.call_count == 1
                assert mock_invoke.call_count == 1
