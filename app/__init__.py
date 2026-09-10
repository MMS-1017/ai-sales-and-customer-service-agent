from flask import Flask

from app.config import Config
from app.extensions import db
from app.models import (
    Customer,
    Product,
    Order,
    OrderItem,
    KnowledgeDocument,
)


def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/db-test")
    def db_test():
        from app.models import Product

        count = Product.query.count()

        return {
            "database": "connected",
            "products_count": count,
        }

    return app