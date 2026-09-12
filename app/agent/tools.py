from langchain_core.tools import tool
from app.services import ProductService, OrderService

@tool
def check_product_availability(product_id: int, quantity: int,) -> dict:
    """Check whether a product has enough stock."""

    return ProductService.check_availability(
        product_id=product_id,
        quantity=quantity,
    )

@tool
def create_order(customer_id: int, product_id: int, quantity: int,) -> dict:
    """Create a real customer order and update product stock."""

    return OrderService.create_order(
        customer_id=customer_id,
        product_id=product_id,
        quantity=quantity,
    )


TOOLS = {
    "check_product_availability": check_product_availability,
    "create_order": create_order,
}