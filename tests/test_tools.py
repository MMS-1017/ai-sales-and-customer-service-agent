from app.agent.tools import product_details_tool, availability_tool, create_order_tool

def test_get_product_details(app):
    with app.app_context():
        result = product_details_tool.invoke({
            "product_id": 1,
        })

        assert result["success"] is True
        assert result["product_id"] == 1
        assert result["product_name"] == "Samsung Galaxy S24"
        assert result["price"] == "$699.99"
        assert result["stock_quantity"] == 15


def test_get_product_details_invalid_product(app):
    with app.app_context():
        result = product_details_tool.invoke({
            "product_id": 999,
        })

        assert result["success"] is False
        assert "not found" in result["error"].lower()


def test_check_product_availability(app):
    with app.app_context():
        result = availability_tool.invoke({
            "product_id": 1,
            "quantity": 2,
        })

        assert result["success"] is True
        assert result["in_stock"] is True
        assert result["requested_quantity"] == 2
        assert result["available_quantity"] == 15


def test_check_product_availability_insufficient_stock(app):
    with app.app_context():
        result = availability_tool.invoke({
            "product_id": 1,
            "quantity": 100,
        })

        assert result["success"] is True
        assert result["in_stock"] is False


def test_create_order_tool(app):
    with app.app_context():
        result = create_order_tool.invoke({
            "customer_id": 1,
            "product_id": 1,
            "quantity": 2,
        })

        assert result["success"] is True
        assert result["order_id"] is not None
        assert result["product_name"] == "Samsung Galaxy S24"
        assert result["quantity"] == 2
        assert result["total_price"] == 1399.98
        assert result["remaining_stock"] == 13