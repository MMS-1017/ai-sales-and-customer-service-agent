from app.agent.nodes import agent_decision
from app.agent.graph import route_after_prepare


def test_product_question_routes_to_product_details():
    state = {
        "intent": "product_question",
    }

    result = agent_decision(state)

    assert result["tool_name"] == "get_product_details"


def test_product_search_routes_to_product_details():
    state = {
        "intent": "product_search",
    }

    result = agent_decision(state)

    assert result["tool_name"] == "get_product_details"


def test_availability_check_routes_to_availability_tool():
    state = {
        "intent": "availability_check",
    }

    result = agent_decision(state)

    assert result["tool_name"] == "check_product_availability"


def test_create_order_routes_to_create_order():
    state = {
        "intent": "create_order",
    }

    result = agent_decision(state)

    assert result["tool_name"] == "create_order"


def test_policy_question_does_not_use_tool():
    state = {
        "intent": "policy_question",
    }

    result = agent_decision(state)

    assert result["tool_name"] is None


def test_general_customer_service_does_not_use_tool():
    state = {
        "intent": "general_customer_service",
    }

    result = agent_decision(state)

    assert result["tool_name"] is None

def test_prepare_tool_error_routes_to_response():
    state = {
        "error": "Product could not be identified.",
    }

    result = route_after_prepare(state)

    assert result == "generate_response"


def test_prepare_tool_success_routes_to_execution():
    state = {
        "tool_input": {"product_id": 1},
    }

    result = route_after_prepare(state)

    assert result == "execute_tool"
