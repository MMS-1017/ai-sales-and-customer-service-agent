from app.agent.graph import build_graph
from app.extensions import db
from app.models import Customer, Product, Order
from decimal import Decimal


def test_customer_conversation_creates_real_order(app, mock_llm):
    with app.app_context():
        graph = build_graph()

        product = Product.query.filter_by(
            name="Samsung Galaxy S24"
        ).first()

        customer = Customer.query.filter_by(
            email="ahmed@test.com"
        ).first()

        initial_stock = product.stock_quantity

        state = {
            "messages": [
                {
                    "role": "user",
                    "content": "I want to buy 2 Samsung Galaxy S24",
                }
            ],
            "customer_id": customer.id,
        }

        result = graph.invoke(state)

        assert result["intent"] == "create_order"
        assert result["tool_name"] == "create_order"
        assert result["tool_result"]["success"] is True

        order_id = result["tool_result"]["order_id"]

        order = db.session.get(Order, order_id)

        assert order is not None
        assert order.customer_id == customer.id
        assert order.total_price == Decimal("1399.98")

        assert order.status == "confirmed"

        db.session.refresh(product)

        assert product.stock_quantity == initial_stock - 2