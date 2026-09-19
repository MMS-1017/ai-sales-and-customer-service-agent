from app.agent.nodes import prepare_tool_input


def test_prepare_product_details_input():
    state = {
        "tool_name": "get_product_details",
        "product_id": 1,
    }

    result = prepare_tool_input(state)

    assert result["tool_input"] == {
        "product_id": 1,
    }


def test_prepare_availability_input():
    state = {
        "tool_name": "check_product_availability",
        "product_id": 1,
        "quantity": 2,
    }

    result = prepare_tool_input(state)

    assert result["tool_input"] == {
        "product_id": 1,
        "quantity": 2,
    }


def test_prepare_create_order_input():
    state = {
        "tool_name": "create_order",
        "product_id": 1,
        "quantity": 2,
        "customer_id": 1,
    }

    result = prepare_tool_input(state)

    assert result["tool_input"] == {
        "customer_id": 1,
        "product_id": 1,
        "quantity": 2,
    }


def test_prepare_order_without_quantity():
    state = {
        "tool_name": "create_order",
        "product_id": 1,
        "customer_id": 1,
    }

    result = prepare_tool_input(state)

    assert result["tool_input"] == {}
    assert result["error"] == "Please specify the quantity."


def test_prepare_availability_without_quantity():
    state = {
        "tool_name": "check_product_availability",
        "product_id": 1,
    }

    result = prepare_tool_input(state)

    assert result["tool_input"] == {
        "product_id": 1,
        "quantity": 1,
    }
    assert "error" not in result


def test_prepare_tool_input_without_product():
    state = {
        "tool_name": "create_order",
        "quantity": 2,
        "customer_id": 1,
    }

    result = prepare_tool_input(state)

    assert result["tool_input"] == {}
    assert result["error"] == "Product could not be identified."

def test_generate_response_does_not_ask_llm_to_recover_from_tool_error(monkeypatch):
    from app.agent import nodes

    def fail_if_called():
        raise AssertionError("LLM should not be called after a backend error")

    monkeypatch.setattr(nodes, "get_llm", fail_if_called)

    result = nodes.generate_response({
        "tool_result": {
            "success": False,
            "error": "System error while checking availability.",
        },
    })

    assert "couldn't complete" in result["response"].lower()
    assert "system error" in result["response"].lower()
