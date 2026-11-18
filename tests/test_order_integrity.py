import pytest
from unittest.mock import patch
from app.extensions import db
from app.models import Product, Order, OrderItem
from app.services.order_service import OrderService
from app.agent.nodes import prepare_tool_input


def test_order_creation_uses_db_price_not_client_input(app):
    """Verify order creation always uses authoritative DB product price."""
    with app.app_context():
        product = Product.query.filter_by(name="Samsung Galaxy S24").first()
        initial_stock = product.stock_quantity

        result = OrderService.create_order(
            customer_id=1,
            product_id=product.id,
            quantity=2,
        )

        assert result["success"] is True
        assert result["unit_price"] == float(product.price)
        assert result["total_price"] == float(product.price * 2)

        order = db.session.get(Order, result["order_id"])
        assert order.total_price == product.price * 2
        assert order.items[0].unit_price == product.price


def test_failed_order_transaction_leaves_no_partial_changes(app):
    """When a database commit fails, the transaction is completely rolled back,

    stock is NOT decremented, and no orphan records are persisted.
    """
    with app.app_context():
        product = Product.query.filter_by(name="Samsung Galaxy S24").first()
        initial_stock = product.stock_quantity
        initial_orders_count = Order.query.count()

        # Simulate a database failure during db.session.commit()
        with patch.object(db.session, "commit", side_effect=RuntimeError("DB disk full")):
            result = OrderService.create_order(
                customer_id=1,
                product_id=product.id,
                quantity=3,
            )

            assert result["success"] is False
            assert "Failed to create order" in result["error"]

        # Verify database integrity after rollback
        db.session.expire_all()
        refreshed_product = db.session.get(Product, product.id)
        assert refreshed_product.stock_quantity == initial_stock

        current_orders_count = Order.query.count()
        assert current_orders_count == initial_orders_count


def test_prepare_tool_input_requires_customer_id():
    """Verify that create_order tool preparation requires a valid customer_id."""
    state = {
        "tool_name": "create_order",
        "product_id": 1,
        "quantity": 2,
        "customer_id": None,
    }

    result = prepare_tool_input(state)
    assert result["tool_input"] == {}
    assert "Customer identification is missing" in result["error"]
