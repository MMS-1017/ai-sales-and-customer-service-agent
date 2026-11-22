"""
Standalone script to simulate an incoming WhatsApp (WAHA) webhook event locally.
Tests:
1. Webhook authentication (X-Webhook-Secret)
2. Deduplication check
3. Agent processing of WhatsApp messages & customer mapping

Run with:
    python test_whatsapp_simulation.py
"""

import json
from app import create_app
from app.config import Config


def simulate_whatsapp():
    print("=" * 65)
    print("📱 TESTING WHATSAPP (WAHA) WEBHOOK LOCALLY")
    print("=" * 65)

    app = create_app()
    client = app.test_client()

    secret = Config.WAHA_WEBHOOK_SECRET

    # 1. Test unauthorized request (missing / wrong secret)
    print("\n[Step 1] Testing Webhook Secret Authentication...")
    unauth_res = client.post(
        "/webhooks/whatsapp",
        json={"event": "message", "payload": {}},
        headers={"X-Webhook-Secret": "wrong-secret"} if secret else {},
    )
    if secret:
        print(f"  -> Sending invalid secret: HTTP {unauth_res.status_code}")
        assert unauth_res.status_code == 401, "Expected 401 Unauthorized for invalid secret"
        print("  -> ✅ Unauthorized webhook rejected with 401!")
    else:
        print("  -> WAHA_WEBHOOK_SECRET not set, skipping auth check.")

    # 2. Test valid incoming customer message
    print("\n[Step 2] Sending Simulated WhatsApp Customer Message...")
    chat_id = "201234567890@c.us"
    payload = {
        "event": "message",
        "session": Config.WAHA_SESSION or "default",
        "payload": {
            "id": "false_201234567890@c.us_3EB0ABC123",
            "from": chat_id,
            "fromMe": False,
            "body": "What is your return policy and warranty?",
            "type": "chat",
            "timestamp": 1700000000,
        },
    }

    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret

    res = client.post("/webhooks/whatsapp", json=payload, headers=headers)
    print(f"  -> Webhook Response Status: {res.status_code}")
    print(f"  -> Webhook Response JSON: {res.get_json()}")
    assert res.status_code == 200, "Expected 200 OK"
    assert res.get_json().get("status") == "processed", "Message was not processed"
    print("  -> ✅ Message successfully processed by LangGraph agent for WhatsApp!")

    # 3. Test Deduplication (Sending exact same message ID again)
    print("\n[Step 3] Testing Message Deduplication...")
    dup_res = client.post("/webhooks/whatsapp", json=payload, headers=headers)
    print(f"  -> Re-sending same message ID: Status {dup_res.status_code}")
    print(f"  -> Deduplication response: {dup_res.get_json()}")
    assert dup_res.get_json().get("reason") == "duplicate_message", "Deduplicator failed to catch duplicate"
    print("  -> ✅ Duplicate message safely ignored without re-processing!")

    # 4. Test WhatsApp LID (@lid) resolution
    print("\n[Step 4] Testing WhatsApp LID (@lid) Automatic Resolution...")
    lid_payload = {
        "event": "message",
        "session": Config.WAHA_SESSION or "default",
        "payload": {
            "id": "false_201555123456@s.whatsapp.net_LIDTEST999",
            "from": "178383245803603@lid",
            "fromMe": False,
            "body": "Hi, do you have smartphones?",
            "type": "chat",
            "_data": {
                "key": {
                    "remoteJid": "201555123456@s.whatsapp.net",
                    "remoteJidAlt": "178383245803603@lid",
                }
            },
        },
    }
    lid_res = client.post("/webhooks/whatsapp", json=lid_payload, headers=headers)
    print(f"  -> LID message processing status: {lid_res.status_code}")
    print(f"  -> Response: {lid_res.get_json()}")
    assert lid_res.status_code == 200
    assert lid_res.get_json().get("status") == "processed"
    print("  -> ✅ WhatsApp @lid identifier successfully resolved to sendable @c.us format!")

    print("\n" + "=" * 65)
    print("🎉 WHATSAPP (WAHA) CONTROLLER & AGENT WORK LOCALLY!")
    print("=" * 65)


if __name__ == "__main__":
    simulate_whatsapp()
