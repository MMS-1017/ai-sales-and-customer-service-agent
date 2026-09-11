from app.models import Product
from app.extensions import db

class ProductService:

    @staticmethod
    def get_product(product_id: int):
        return Product.query.filter_by(
            id=product_id,
            is_active=True,
        ).first()

    @staticmethod
    def search_products(query: str | None = None, category: str | None = None):
        products_query = Product.query.filter_by(is_active=True)

        if query:
            search_pattern = f"%{query}%"

            products_query = products_query.filter(
                db.or_(
                    Product.name.ilike(search_pattern),
                    Product.description.ilike(search_pattern),
                )
            )

        if category:
            products_query = products_query.filter(
                Product.category.ilike(category)
            )

        return products_query.order_by(Product.name).all()

    @staticmethod
    def check_availability(product_id: int, quantity: int):
        product = ProductService.get_product(product_id)

        if not product:
            return {
                "success": False,
                "error": "Product not found.",
            }

        if quantity <= 0:
            return {
                "success": False,
                "error": "Quantity must be greater than zero.",
            }

        return {
            "success": True,
            "product_id": product.id,
            "product_name": product.name,
            "requested_quantity": quantity,
            "available_quantity": product.stock_quantity,
            "in_stock": product.stock_quantity >= quantity,
        }

    @staticmethod
    def list_active_products():
        return Product.query.filter_by(
            is_active=True
        ).order_by(Product.name).all()