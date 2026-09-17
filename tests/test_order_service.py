from app.extensions import db
from app.models import Customer, Order, OrderItem, Product
from app.services.order_service import OrderService
from decimal import Decimal


def test_create_order_success(app):
    with app.app_context():
        result = OrderService.create_order(
            customer_id=1,
            product_id=1,
            quantity=2,
        )

        assert result["success"] is True
        assert result["order_id"] is not None
        assert result["product_name"] == "Samsung Galaxy S24"
        assert result["quantity"] == 2
        assert result["unit_price"] == 699.99
        assert result["total_price"] == 1399.98
        assert result["remaining_stock"] == 13
        assert result["status"] == "confirmed"

        order = db.session.get(Order, result["order_id"])

        assert order is not None
        assert order.customer_id == 1
        assert order.total_price == Decimal("1399.98")

        order_item = OrderItem.query.filter_by(
            order_id=order.id
        ).first()

        assert order_item is not None
        assert order_item.product_id == 1
        assert order_item.quantity == 2
        assert order_item.unit_price == Decimal("699.99")

        product = db.session.get(Product, 1)

        assert product.stock_quantity == 13


def test_create_order_invalid_quantity(app):
    with app.app_context():
        result = OrderService.create_order(
            customer_id=1,
            product_id=1,
            quantity=0,
        )

        assert result["success"] is False
        assert "quantity" in result["error"].lower()


def test_create_order_nonexistent_customer(app):
    with app.app_context():
        result = OrderService.create_order(
            customer_id=999,
            product_id=1,
            quantity=1,
        )

        assert result["success"] is False
        assert "customer" in result["error"].lower()


def test_create_order_nonexistent_product(app):
    with app.app_context():
        result = OrderService.create_order(
            customer_id=1,
            product_id=999,
            quantity=1,
        )

        assert result["success"] is False
        assert "product" in result["error"].lower()


def test_create_order_insufficient_stock(app):
    with app.app_context():
        product = db.session.get(Product, 1)
        initial_stock = product.stock_quantity

        result = OrderService.create_order(
            customer_id=1,
            product_id=1,
            quantity=initial_stock + 1,
        )

        assert result["success"] is False
        assert "stock" in result["error"].lower()

        product = db.session.get(Product, 1)
        assert product.stock_quantity == initial_stock

        orders_count = Order.query.count()
        assert orders_count == 0