from flask import Flask

from app.config import Config
from app.extensions import db
from app.models import Customer, Product, Order, OrderItem, KnowledgeDocument
from app.controllers.chat_controller import chat_bp
from app.controllers.admin_controller import admin_bp


def create_app(test_config=None):
    app = Flask(
        __name__,
        template_folder="views/templates",
        static_folder="views/static",
    )

    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/db-test")
    def db_test():
        count = Product.query.count()

        return {
            "database": "connected",
            "products_count": count,
        }

    return app