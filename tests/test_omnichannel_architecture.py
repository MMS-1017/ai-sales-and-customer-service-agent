from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
from unittest.mock import patch

from flask import Request
import pytest
import requests

from app import create_app
from app.channels import (
    ChannelAdapter,
    ChannelDeliveryError,
    ChannelDeliveryResult,
    ChannelRegistry,
    DownloadedMedia,
    MessengerAdapter,
    WebChatAdapter,
    WhatsAppAdapter,
    get_channel_registry,
    split_text_chunks,
)
from app.channels.dispatcher import handle_channel_request
from app.controllers.facebook_controller import webhook_deduplicator as fb_dedup
from app.controllers.whatsapp_controller import webhook_deduplicator as wa_dedup
from app.extensions import db
from app.models import (
    Conversation,
    Customer,
    CustomerChannelIdentity,
    Message,
    MessageAttachment,
)
from app.schemas import (
    MediaType,
    MessageType,
    UnifiedAttachment,
    UnifiedIncomingMessage,
    UnifiedOutboundMessage,
)
from app.services import (
    ChannelService,
    CustomerIdentityService,
    OutboundMessagingService,
)
from app.services.conversation_service import ConversationService
from app.services.identity_service import IdentityConflictError


@pytest.fixture
def omni_app():
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WAHA_WEBHOOK_SECRET": "",
            "FACEBOOK_APP_SECRET": "fb_secret_test",
            "FACEBOOK_VERIFY_TOKEN": "fb_verify_tok",
        }
    )
    with test_app.app_context():
        db.create_all()
        cust = Customer(name="Ahmed Hassan", email="ahmed@example.com")
        db.session.add(cust)
        db.session.commit()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def omni_client(omni_app):
    wa_dedup.clear()
    fb_dedup.clear()
    ConversationService.clear()
    return omni_app.test_client()


# ----------------------------------------------------------------------
# 1-3. Normalization across WhatsApp, Messenger, Web Chat & unknown fields
# ----------------------------------------------------------------------

def test_whatsapp_normalization_with_unknown_fields_and_lid_resolution():
    adapter = WhatsAppAdapter()
    payload = {
        "event": "message",
        "session": "sales_session",
        "unknown_provider_meta": {"nested": True},
        "payload": {
            "id": "false_201055566677@s.whatsapp.net_HASH99",
            "from": "9988112233@lid",
            "body": "  Hi, check Samsung Galaxy S24  ",
            "type": "chat",
            "timestamp": 1764000000,
            "unexpected_field": "ignored_safely",
        },
    }
    msgs, ignored = adapter.parse_payload_dict(payload)
    assert ignored is None
    assert len(msgs) == 1
    m = msgs[0]
    assert m.channel == "whatsapp"
    assert m.channel_account_id == "sales_session"
    assert m.external_user_id == "201055566677@c.us"
    assert m.external_message_id == "false_201055566677@s.whatsapp.net_HASH99"
    assert m.message_type == MessageType.TEXT
    assert m.text == "Hi, check Samsung Galaxy S24"
    assert m.timestamp.tzinfo == timezone.utc


def test_messenger_normalization_skips_echo_and_handles_ms_timestamp():
    adapter = MessengerAdapter()
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_101",
                "messaging": [
                    {
                        "sender": {"id": "page_101"},
                        "timestamp": 1764000000000,
                        "message": {"mid": "m_echo", "is_echo": True, "text": "Agent echo"},
                    },
                    {
                        "sender": {"id": "PSID_777"},
                        "timestamp": 1764000001500,
                        "message": {
                            "mid": "m_in_1",
                            "text": "Look at this",
                            "unknown_fb_tag": 42,
                            "attachments": [{"type": "image", "payload": {"url": "https://cdn.fb/img.jpg"}}],
                        },
                    },
                ],
            }
        ],
    }
    msgs, ignored = adapter.parse_payload_dict(payload)
    assert ignored is None
    assert len(msgs) == 1
    m = msgs[0]
    assert m.channel == "facebook"
    assert m.channel_account_id == "page_101"
    assert m.external_user_id == "PSID_777"
    assert m.external_message_id == "m_in_1"
    assert m.message_type == MessageType.MIXED
    assert m.attachments[0].media_type == MediaType.IMAGE
    assert m.timestamp.year >= 2025


def test_web_chat_normalization_supports_visitor_id():
    adapter = WebChatAdapter()
    msgs, ignored = adapter.parse_payload_dict(
        {"message": "Do you ship?", "visitor_id": "visitor_abc123", "conversation_id": "web_sess_1"}
    )
    assert ignored is None
    m = msgs[0]
    assert m.channel == "web_chat"
    assert m.external_user_id == "visitor_abc123"
    assert m.customer_id is None
    assert m.conversation_id == "web_sess_1"
    assert m.metadata["has_visitor_id"] is True


# ----------------------------------------------------------------------
# 4-5. Customer Identity Resolution, Linking, No Unsafe Auto-Merge
# ----------------------------------------------------------------------

def test_customer_identity_resolution_prevents_duplication_and_unsafe_merge(omni_app):
    with omni_app.app_context():
        msg1 = UnifiedIncomingMessage(
            channel="whatsapp",
            external_user_id="+201012345678@c.us",
            conversation_id="whatsapp:+201012345678@c.us",
            text="Hello",
            metadata={"sender_name": "Ahmed Hassan"},  # Same name as existing Customer #1!
        )
        cust_wa, ident_wa = CustomerIdentityService.resolve_or_create_customer(msg1)
        # Must NOT merge automatically based on matching name "Ahmed Hassan"
        assert cust_wa.id != 1
        assert ident_wa.channel == "whatsapp"

        # Repeated WhatsApp contact must resolve to the SAME customer without duplication
        cust_wa_again, _ = CustomerIdentityService.resolve_or_create_customer(msg1)
        assert cust_wa_again.id == cust_wa.id


def test_cross_channel_identity_linking_and_conflict_guard(omni_app):
    with omni_app.app_context():
        # Link WA, Messenger, and Web visitor to Customer #1 ("Ahmed Hassan")
        CustomerIdentityService.link_identity(
            customer_id=1,
            channel="whatsapp",
            external_user_id="201099988877@c.us",
            verified=True,
        )
        CustomerIdentityService.link_identity(
            customer_id=1,
            channel="messenger",
            external_user_id="PSID_123456",
            verified=True,
        )
        CustomerIdentityService.link_identity(
            customer_id=1,
            channel="web_chat",
            external_user_id="visitor_abc123",
            verified=True,
        )

        identities = CustomerIdentityService.list_identities(1)
        assert len(identities) == 3

        # Resolving from Messenger PSID_123456 must resolve to Customer #1
        fb_msg = UnifiedIncomingMessage(
            channel="facebook",
            external_user_id="PSID_123456",
            conversation_id="facebook:PSID_123456",
            text="Hey",
        )
        resolved, _ = CustomerIdentityService.resolve_or_create_customer(fb_msg)
        assert resolved.id == 1

        # Linking PSID_123456 to a different customer without force_reassign must fail
        other = Customer(name="Other", email="other@example.com")
        db.session.add(other)
        db.session.commit()
        with pytest.raises(IdentityConflictError):
            CustomerIdentityService.link_identity(
                customer_id=other.id,
                channel="messenger",
                external_user_id="PSID_123456",
            )


def test_explicit_customer_merge_preserves_data(omni_app):
    with omni_app.app_context():
        dup = Customer(name="Ahmed Dup", email="whatsapp_201000@whatsapp.local")
        db.session.add(dup)
        db.session.commit()
        CustomerIdentityService.link_identity(
            customer_id=dup.id, channel="whatsapp", external_user_id="201000@c.us"
        )
        conv = ConversationService.resolve_or_create_conversation(
            customer_id=dup.id, channel="whatsapp", external_conversation_id="whatsapp:201000@c.us"
        )
        db.session.commit()

        merged = CustomerIdentityService.merge_customers(
            source_customer_id=dup.id, target_customer_id=1
        )
        assert merged.id == 1
        assert db.session.get(Customer, dup.id) is None
        refreshed_conv = db.session.get(Conversation, conv.id)
        assert refreshed_conv.customer_id == 1


# ----------------------------------------------------------------------
# 6-9. Persistent Conversations, Cross-Channel Context, Idempotency, Agent
# ----------------------------------------------------------------------

def test_persistent_conversation_and_controlled_cross_channel_context(omni_app):
    with omni_app.app_context():
        # Bind WhatsApp + Messenger to Customer #1
        CustomerIdentityService.link_identity(customer_id=1, channel="whatsapp", external_user_id="201011@c.us")
        CustomerIdentityService.link_identity(customer_id=1, channel="facebook", external_user_id="PSID_999")

        captured_states = []

        def fake_agent_invoke(state):
            captured_states.append(state)
            return {"response": "Happy to help!", "intent": "product_question", "tool_result": None}

        with patch("app.services.channel_service.agent_graph.invoke", side_effect=fake_agent_invoke):
            with patch("app.services.waha_service.WahaService.send_text"):
                wa_msg = UnifiedIncomingMessage(
                    channel="whatsapp",
                    external_user_id="201011@c.us",
                    external_message_id="wa_msg_100",
                    conversation_id="whatsapp:201011@c.us",
                    text="Interested in MacBook Air M3",
                )
                ChannelService.process_message(wa_msg)

            with patch("app.services.facebook_service.FacebookService.send_message"):
                fb_msg = UnifiedIncomingMessage(
                    channel="facebook",
                    external_user_id="PSID_999",
                    external_message_id="fb_msg_200",
                    conversation_id="facebook:PSID_999",
                    text="What is the warranty on that laptop?",
                )
                ChannelService.process_message(fb_msg)

        # Conversations are kept strictly separate per channel
        convs = Conversation.query.filter_by(customer_id=1).all()
        assert len(convs) == 2
        channels = {c.channel for c in convs}
        assert channels == {"whatsapp", "facebook"}

        # Messenger turn did NOT dump WA turns into `messages`, but DID receive cross_channel_context!
        fb_state = captured_states[1]
        assert fb_state["messages"] == ["What is the warranty on that laptop?"]
        assert fb_state["customer_id"] == 1
        assert fb_state["customer_profile"] == {"name": "Ahmed Hassan"}
        assert len(fb_state["cross_channel_context"]) == 1
        assert "MacBook Air M3" in fb_state["cross_channel_context"][0]

        # Persisted messages: 2 inbound + 2 outbound = 4 rows
        assert Message.query.filter_by(customer_id=1).count() == 4


def test_db_idempotency_prevents_duplicate_agent_after_cache_clear(omni_app):
    with omni_app.app_context():
        msg = UnifiedIncomingMessage(
            channel="whatsapp",
            external_user_id="201022@c.us",
            external_message_id="wa_idempotent_77",
            conversation_id="whatsapp:201022@c.us",
            text="Order Samsung",
        )
        with patch("app.services.channel_service.agent_graph.invoke", return_value={"response": "OK"}) as mock_ai:
            with patch("app.services.waha_service.WahaService.send_text") as mock_send:
                r1 = ChannelService.process_message(msg)
                # Even if in-memory cache was wiped (e.g. restart), DB idempotency blocks retry!
                wa_dedup.clear()
                r2 = ChannelService.process_message(msg)

                assert r1.delivery_status == "sent"
                assert r2.delivery_status == "duplicate_ignored"
                assert mock_ai.call_count == 1
                assert mock_send.call_count == 1


# ----------------------------------------------------------------------
# 10-11. Outbound Selection, Chunking, Retries & Failure Handling
# ----------------------------------------------------------------------

def test_outbound_service_retries_transient_error_and_chunks_messenger(omni_app):
    with omni_app.app_context():
        conv = ConversationService.resolve_or_create_conversation(
            customer_id=1, channel="facebook", external_conversation_id="facebook:PSID_RETRY"
        )
        long_text = ("word " * 500).strip()  # > 2000 chars -> Messenger limit requires 2 chunks
        outbound = UnifiedOutboundMessage(
            channel="messenger",
            recipient_id="PSID_RETRY",
            conversation_id=conv.id,
            text=long_text,
            reply_to_external_message_id="mid_retry_1",
        )

        calls = {"count": 0}

        def flaky_send(recipient_id, text):
            calls["count"] += 1
            if calls["count"] == 1:
                resp = requests.Response()
                resp.status_code = 503
                raise requests.HTTPError("503 Service Unavailable", response=resp)
            return {"message_id": f"mid_out_{calls['count']}"}

        with patch("app.services.facebook_service.FacebookService.send_message", side_effect=flaky_send):
            res = OutboundMessagingService.send(
                outbound, conversation=conv, max_retries=2, retry_backoff_base=0
            )
            assert res.success is True
            assert res.delivery_status == "sent"
            assert res.chunks_sent == len(split_text_chunks(long_text, 2000))

            # Calling OutboundMessagingService.send again with same reply_to skips duplicate send
            res_dup = OutboundMessagingService.send(
                outbound, conversation=conv, max_retries=0, retry_backoff_base=0
            )
            assert res_dup.delivery_status == "already_sent"


def test_outbound_permanent_failure_recorded_gracefully(omni_app):
    with omni_app.app_context():
        conv = ConversationService.resolve_or_create_conversation(
            customer_id=1, channel="whatsapp", external_conversation_id="whatsapp:201033@c.us"
        )
        outbound = UnifiedOutboundMessage(
            channel="whatsapp",
            recipient_id="201033@c.us",
            conversation_id=conv.id,
            text="Hi",
            reply_to_external_message_id="wa_fail_1",
        )

        resp_400 = requests.Response()
        resp_400.status_code = 400
        with patch(
            "app.services.waha_service.WahaService.send_text",
            side_effect=requests.HTTPError("Bad Request", response=resp_400),
        ) as mock_send:
            res = OutboundMessagingService.send(
                outbound, conversation=conv, max_retries=2, retry_backoff_base=0
            )
            assert res.success is False
            assert res.delivery_status == "failed"
            # Non-retryable 400 must NOT retry 3 times
            assert mock_send.call_count == 1
            stored = Message.query.filter_by(conversation_id=conv.id, direction="outbound").first()
            assert stored.delivery_status == "failed"


# ----------------------------------------------------------------------
# 12-13. Webhook Security, Attachment Persistence, Future Channel & Admin UI
# ----------------------------------------------------------------------

def test_webhook_security_checks(omni_client, omni_app):
    # Invalid Meta signature -> 403
    with patch("app.services.facebook_service.Config.FACEBOOK_APP_SECRET", "real_secret"):
        bad_fb = omni_client.post(
            "/webhooks/facebook",
            data=b'{"object":"page","entry":[]}',
            content_type="application/json",
            headers={"X-Hub-Signature-256": "sha256=deadbeef"},
        )
        assert bad_fb.status_code == 403

    # Strict mode with missing secret -> 403
    omni_app.config["REQUIRE_WEBHOOK_SECRETS"] = True
    omni_app.config["FACEBOOK_APP_SECRET"] = ""
    with patch("app.services.facebook_service.Config.FACEBOOK_APP_SECRET", ""):
        missing_fb = omni_client.post(
            "/webhooks/facebook",
            data=b'{"object":"page","entry":[]}',
            content_type="application/json",
        )
        assert missing_fb.status_code == 403

    # Invalid WAHA secret -> 401
    omni_app.config["WAHA_WEBHOOK_SECRET"] = "waha_secret_xyz"
    bad_wa = omni_client.post(
        "/webhooks/whatsapp",
        json={"event": "message", "payload": {"from": "123@c.us", "body": "Hi"}},
        headers={"X-Webhook-Secret": "wrong"},
    )
    assert bad_wa.status_code == 401


def test_attachment_persisted_in_message_attachments(omni_client):
    with patch("app.services.media_service.MediaService.transcribe_audio", return_value="Check iPhone price"):
        with patch("app.services.channel_service.agent_graph.invoke", return_value={"response": "iPhone is $799.99"}):
            res = omni_client.post(
                "/api/chat",
                data={
                    "message": "",
                    "customer_id": "1",
                    "conversation_id": "web_audio_1",
                    "file": (io.BytesIO(b"OggSfake_bytes"), "voice.ogg", "audio/ogg"),
                },
                content_type="multipart/form-data",
            )
            assert res.status_code == 200
            att = MessageAttachment.query.first()
            assert att is not None
            assert att.media_type == "audio"
            assert att.extracted_text == "Check iPhone price"
            assert att.media_file_id is not None


def test_adding_new_channel_adapter_works_without_core_changes(omni_app):
    """Proves a future channel (e.g. Telegram) plugs in cleanly via ChannelRegistry."""
    sent_payloads = []

    class FakeTelegramAdapter(ChannelAdapter):
        channel_name = "telegram"
        max_text_length = 4096

        def parse_incoming(self, req: Request):
            data = req.get_json(silent=True) or {}
            msg = data.get("message", {})
            chat = msg.get("chat", {})
            return [
                UnifiedIncomingMessage(
                    channel="telegram",
                    external_user_id=str(chat.get("id")),
                    external_message_id=str(msg.get("message_id")),
                    conversation_id=f"telegram:{chat.get('id')}",
                    text=msg.get("text", ""),
                )
            ], None

        def download_attachment(self, attachment: UnifiedAttachment, message: UnifiedIncomingMessage) -> DownloadedMedia:
            return DownloadedMedia(content=b"", mime_type="application/octet-stream", file_name="empty.bin")

        def send_message(self, outbound: UnifiedOutboundMessage) -> ChannelDeliveryResult:
            sent_payloads.append(outbound)
            return ChannelDeliveryResult(success=True, external_message_id="tg_out_1")

    registry = ChannelRegistry()
    registry.register(FakeTelegramAdapter())

    with omni_app.test_request_context(
        "/webhooks/channel/telegram",
        method="POST",
        json={"message": {"message_id": 55, "chat": {"id": 987654}, "text": "Hello Telegram"}},
    ):
        from flask import request as flask_req

        with patch("app.services.channel_service.agent_graph.invoke", return_value={"response": "Hi from Unified Agent!"}):
            body, status = handle_channel_request("telegram", flask_req, registry=registry)
            assert status == 200
            assert len(sent_payloads) == 1
            assert sent_payloads[0].recipient_id == "987654"
            assert sent_payloads[0].text == "Hi from Unified Agent!"


def test_admin_conversations_and_link_identity_routes(omni_client, omni_app):
    res_link = omni_client.post(
        "/admin/customers/link-identity",
        data={"customer_id": "1", "channel": "whatsapp", "external_user_id": "201044455566@c.us"},
        follow_redirects=False,
    )
    assert res_link.status_code == 302

    res_cust = omni_client.get("/admin/customers")
    assert res_cust.status_code == 200
    assert b"201044455566@c.us" in res_cust.data
    assert b"View Chats" in res_cust.data

    with patch("app.services.channel_service.agent_graph.invoke", return_value={"response": "Saved agent reply!"}):
        with patch("app.services.waha_service.WahaService.send_text"):
            wa_res = omni_client.post(
                "/webhooks/whatsapp",
                json={
                    "event": "message",
                    "session": "default",
                    "payload": {
                        "id": "wa_admin_view_1",
                        "from": "201044455566@c.us",
                        "fromMe": False,
                        "body": "Need laptop specs",
                        "type": "chat",
                    },
                },
            )
            assert wa_res.status_code == 200

            web_res = omni_client.post(
                "/api/chat",
                json={"message": "Checking web history", "customer_id": 1, "conversation_id": "web_thread_1"},
            )
            assert web_res.status_code == 200

    res_convs = omni_client.get("/admin/conversations")
    assert res_convs.status_code == 200
    assert b"whatsapp:201044455566@c.us" in res_convs.data
    assert b"web_thread_1" in res_convs.data
    assert b"Saved agent reply!" in res_convs.data
    assert b"View Chat" in res_convs.data

    res_wa_filter = omni_client.get("/admin/conversations?channel=whatsapp&q=laptop")
    assert res_wa_filter.status_code == 200
    assert b"whatsapp:201044455566@c.us" in res_wa_filter.data
    assert b"web_thread_1" not in res_wa_filter.data

    with omni_app.app_context():
        wa_conv = Conversation.query.filter_by(channel="whatsapp").first()
        assert wa_conv is not None
        wa_conv_id = wa_conv.id

    res_detail = omni_client.get(f"/admin/conversations/{wa_conv_id}")
    assert res_detail.status_code == 200
    assert b"Need laptop specs" in res_detail.data
    assert b"Saved agent reply!" in res_detail.data
    assert b"Other Customer Chats" in res_detail.data

    res_missing = omni_client.get("/admin/conversations/999999")
    assert res_missing.status_code == 404


def test_tools_preserve_contract_while_prompt_redacts_exact_stock(omni_app):
    from app.agent.nodes import generate_response
    from app.agent.tools import availability_tool, product_details_tool
    from app.models import Product

    with omni_app.app_context():
        p = Product(
            name="Test Speaker",
            description="Compact Bluetooth speaker.",
            price=49.99,
            category="Audio",
            stock_quantity=15,
            is_active=True,
        )
        db.session.add(p)
        db.session.commit()

        details = product_details_tool.invoke({"product_id": p.id})
        avail = availability_tool.invoke({"product_id": p.id, "quantity": 2})
        assert details["stock_quantity"] == 15
        assert avail["available_quantity"] == 15

        captured_prompts = []

        class InspectLLM:
            def invoke(self, prompt):
                captured_prompts.append(prompt)
                return type("Resp", (), {"content": "Available for $49.99!"})()

        with patch("app.agent.nodes.get_llm", return_value=InspectLLM()):
            res = generate_response(
                {
                    "messages": ["How much is Test Speaker?"],
                    "tool_result": details,
                    "retrieved_context": [],
                }
            )
            assert res["response"] == "Available for $49.99!"
            assert "'stock_quantity': 15" not in captured_prompts[0]
            assert "'is_available': True" in captured_prompts[0]


def test_legacy_customer_identity_backfill_idempotent(omni_app):
    from scripts.migrate_omnichannel import run_omnichannel_migration

    with omni_app.app_context():
        legacy_wa = Customer(name="Legacy WA", email="whatsapp_201088899900@whatsapp.local")
        legacy_fb = Customer(name="Legacy FB", email="facebook_PSID_LEGACY@facebook.local")
        db.session.add_all([legacy_wa, legacy_fb])
        db.session.commit()

    with patch("scripts.migrate_omnichannel.create_app", return_value=omni_app):
        run_omnichannel_migration()
        run_omnichannel_migration()  # Idempotent second run

    with omni_app.app_context():
        assert CustomerChannelIdentity.query.filter_by(channel="whatsapp", external_user_id="201088899900@c.us").count() == 1
        assert CustomerChannelIdentity.query.filter_by(channel="facebook", external_user_id="PSID_LEGACY").count() == 1

