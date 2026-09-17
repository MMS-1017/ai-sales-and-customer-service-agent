def test_health_endpoint(client):

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_chat_rejects_empty_message(client):
    response = client.post(
        "/api/chat",
        json={"message": ""},
    )

    assert response.status_code == 400


def test_chat_rejects_missing_message(client):
    response = client.post(
        "/api/chat",
        json={},
    )

    assert response.status_code == 400


def test_chat_accepts_valid_message(client):
    response = client.post(
        "/api/chat",
        json={
            "message": "What is the price of Samsung Galaxy S24?",
            "conversation_id": "test-controller-conversation",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert "response" in data