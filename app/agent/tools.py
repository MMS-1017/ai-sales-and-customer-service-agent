from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from app.services import ProductService, OrderService


class ProductDetailsInput(BaseModel):
    product_id: int


class AvailabilityInput(BaseModel):
    product_id: int
    quantity: int = Field(default=1, gt=0)


class CreateOrderInput(BaseModel):
    customer_id: int
    product_id: int
    quantity: int = Field(gt=0)


def get_product_details(product_id: int):
    product = ProductService.get_product(product_id)

    if not product:
        return {
            "success": False,
            "error": "Product not found.",
        }

    return {
        "success": True,
        "product_id": product.id,
        "product_name": product.name,
        "description": product.description,
        "category": product.category,
        "price": f"${product.price:.2f}",
        "stock_quantity": product.stock_quantity,
        "is_active": product.is_active,
    }


def check_product_availability(product_id: int, quantity: int):
    return ProductService.check_availability(
        product_id=product_id,
        quantity=quantity
    )


def create_order(customer_id: int, product_id: int, quantity: int):
    return OrderService.create_order(
        customer_id=customer_id,
        product_id=product_id,
        quantity=quantity
    )


product_details_tool = StructuredTool.from_function(
    func=get_product_details,
    name="get_product_details",
    description=(
        "Get current product information including "
        "name, description, category, price, and stock "
        "from the database."
    ),
    args_schema=ProductDetailsInput,
)


availability_tool = StructuredTool.from_function(
    func=check_product_availability,
    name="check_product_availability",
    description=(
        "Check whether a requested quantity of a product "
        "is currently available in stock."
    ),
    args_schema=AvailabilityInput,
)


create_order_tool = StructuredTool.from_function(
    func=create_order,
    name="create_order",
    description=(
        "Create a customer order for a product. "
        "This performs the real backend business transaction."
    ),
    args_schema=CreateOrderInput,
)


TOOLS = {
    "get_product_details": product_details_tool,
    "check_product_availability": availability_tool,
    "create_order": create_order_tool,
}