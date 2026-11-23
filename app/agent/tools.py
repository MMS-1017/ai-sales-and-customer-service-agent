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


class BestSellersInput(BaseModel):
    category: str | None = Field(
        default=None,
        description="Optional product category to filter by (e.g. 'headphones', 'laptops').",
    )
    limit: int = Field(
        default=5,
        gt=0,
        le=20,
        description="Maximum number of results to return.",
    )


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
        "is_available": product.stock_quantity > 0,
        "is_active": product.is_active,
    }


def check_product_availability(product_id: int, quantity: int):
    result = ProductService.check_availability(
        product_id=product_id,
        quantity=quantity,
    )
    if result.get("success"):
        return {
            "success": True,
            "product_id": result["product_id"],
            "product_name": result["product_name"],
            "requested_quantity": result["requested_quantity"],
            "in_stock": result["in_stock"],
        }
    return result


def create_order(customer_id: int, product_id: int, quantity: int):
    return OrderService.create_order(
        customer_id=customer_id,
        product_id=product_id,
        quantity=quantity
    )


def get_best_sellers(category: str | None = None, limit: int = 5):
    results = ProductService.get_best_sellers(category=category, limit=limit)

    if not results:
        label = f"in category '{category}'" if category else "in the store"
        return {
            "success": False,
            "error": f"No products found {label}.",
        }

    products = []
    for product, units_sold in results:
        products.append({
            "product_id": product.id,
            "product_name": product.name,
            "category": product.category,
            "price": f"${product.price:.2f}",
            "stock_quantity": product.stock_quantity,
            "is_available": product.stock_quantity > 0,
            "units_sold": int(units_sold),
        })

    return {
        "success": True,
        "category_filter": category,
        "products": products,
    }


product_details_tool = StructuredTool.from_function(
    func=get_product_details,
    name="get_product_details",
    description=(
        "Get current product information including "
        "name, description, category, price, and availability status "
        "from the database. Never disclose exact inventory counts."
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


best_sellers_tool = StructuredTool.from_function(
    func=get_best_sellers,
    name="get_best_sellers",
    description=(
        "Get the best-selling products ranked by total units sold. "
        "Accepts an optional category filter (e.g. 'headphones', 'laptops') "
        "and an optional limit. Use this for recommendation and best-seller queries."
    ),
    args_schema=BestSellersInput,
)


TOOLS = {
    "get_product_details": product_details_tool,
    "check_product_availability": availability_tool,
    "create_order": create_order_tool,
    "get_best_sellers": best_sellers_tool,
}
