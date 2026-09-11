from decimal import Decimal

from app.extensions import db
from app.models import Customer, Order, OrderItem, Product


class OrderService:

    @staticmethod
    def create_order(
        customer_id: int,
        product_id: int,
        quantity: int,
    ):
        if quantity <= 0:
            return {
                "success": False,
                "error": "Quantity must be greater than zero.",
            }

        customer = db.session.get(Customer, customer_id)

        if not customer:
            return {
                "success": False,
                "error": "Customer not found.",
            }

        product = db.session.get(Product, product_id)

        if not product or not product.is_active:
            return {
                "success": False,
                "error": "Product not found.",
            }

        if product.stock_quantity < quantity:
            return {
                "success": False,
                "error": (
                    f"Insufficient stock. "
                    f"Only {product.stock_quantity} units are available."
                ),
            }

        total_price = product.price * quantity

        try:
            order = Order(
                customer_id=customer.id,
                status="confirmed",
                total_price=total_price,
            )

            order_item = OrderItem(
                product_id=product.id,
                quantity=quantity,
                unit_price=product.price,
            )

            order.items.append(order_item)

            product.stock_quantity -= quantity

            db.session.add(order)
            db.session.commit()

            return {
                "success": True,
                "order_id": order.id,
                "customer_id": customer.id,
                "product_id": product.id,
                "product_name": product.name,
                "quantity": quantity,
                "unit_price": float(product.price),
                "total_price": float(total_price),
                "remaining_stock": product.stock_quantity,
                "status": order.status,
            }

        except Exception:
            db.session.rollback()

            return {
                "success": False,
                "error": "Failed to create order.",
            }