from app.agent.nodes import agent_decision, prepare_tool_input


def test_create_order_without_quantity_returns_error():
    state = {
        "tool_name": "create_order",
        "product_id": 1,
        "customer_id": 1,
        "quantity": None,
    }

    result = prepare_tool_input(state)

    assert result["error"] == "Please specify the quantity."


def test_availability_without_quantity_returns_error():
    state = {
        "tool_name": "check_product_availability",
        "product_id": 1,
        "quantity": None,
    }

    result = prepare_tool_input(state)

    assert result["error"] == "Please specify the quantity."


def test_missing_product_returns_error():
    state = {
        "intent": "create_order",
        "product_id": None,
        "customer_id": 1,
        "quantity": 2,
    }

    result = prepare_tool_input(state)

    assert result["error"] == "Product could not be identified."
    assert result["tool_input"] == {}


def test_policy_question_does_not_call_business_tool():
    state = {
        "intent": "policy_question",
    }

    result = agent_decision(state)

    assert result["tool_name"] is None


def test_general_customer_service_does_not_call_business_tool():
    state = {
        "intent": "general_customer_service",
    }

    result = agent_decision(state)

    assert result["tool_name"] is None