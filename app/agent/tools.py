from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from app.services import ProductService, OrderService


class AvailabilityInput(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class CreateOrderInput(BaseModel):
    customer_id: int
    product_id: int
    quantity: int = Field(gt=0)


def check_product_availability(product_id: int, quantity: int):
    return ProductService.check_availability(
        product_id=product_id,
        quantity=quantity,
    )


def create_order(customer_id: int, product_id: int, quantity: int,):
    return OrderService.create_order(
        customer_id=customer_id,
        product_id=product_id,
        quantity=quantity,
    )


availability_tool = StructuredTool.from_function(
    func=check_product_availability,
    name="check_product_availability",
    description="Check product stock availability.",
    args_schema=AvailabilityInput,
)


create_order_tool = StructuredTool.from_function(
    func=create_order,
    name="create_order",
    description="Create a real customer order.",
    args_schema=CreateOrderInput,
)


TOOLS = {
    "check_product_availability": availability_tool,
    "create_order": create_order_tool,
}