from app.models import Product
from app.extensions import db
from rapidfuzz import process, fuzz

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
    def fuzzy_search_products(query: str, threshold: int = 65):
        """Fuzzy-match query against all active product names using rapidfuzz.

        Returns a list of (Product, score) tuples sorted by descending score,
        filtered to those above `threshold` (0-100 scale).
        """
        all_products = Product.query.filter_by(is_active=True).all()

        if not all_products:
            return []

        # Build a map: name -> Product
        name_to_product = {p.name: p for p in all_products}

        results = process.extract(
            query,
            name_to_product.keys(),
            scorer=fuzz.token_sort_ratio,
            limit=5,
        )

        # results: list of (name, score, key)
        matches = [
            (name_to_product[name], score)
            for name, score, _ in results
            if score >= threshold
        ]

        return matches  # list of (Product, score)

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

    @staticmethod
    def get_best_sellers(category: str | None = None, limit: int = 5):
        from app.models import OrderItem
        from sqlalchemy import func

        units_sold = func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold")

        query = (
            db.session.query(Product, units_sold)
            .outerjoin(OrderItem, OrderItem.product_id == Product.id)
            .filter(Product.is_active == True)
        )

        if category:
            query = query.filter(Product.category.ilike(f"%{category}%"))

        results = (
            query
            .group_by(Product.id)
            .order_by(db.desc("units_sold"), Product.name)
            .limit(limit)
            .all()
        )

        return results  # list of (Product, units_sold)