import os

import pytest

from app import create_app
from app.extensions import db
from app.models import Customer, Product


@pytest.fixture
def app():
    test_database_url = os.getenv("TEST_DATABASE_URL")

    if not test_database_url:
        raise RuntimeError("TEST_DATABASE_URL is not configured.")

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": test_database_url,
        }
    )

    with app.app_context():
        db.drop_all()
        db.create_all()

        customer = Customer(
            name="Ahmed Hassan",
            email="ahmed@test.com",
        )

        samsung = Product(
            name="Samsung Galaxy S24",
            description="Samsung Galaxy S24 smartphone.",
            price=699.99,
            category="Smartphones",
            stock_quantity=15,
            is_active=True,
        )

        iphone = Product(
            name="iPhone 15",
            description="Apple iPhone 15 smartphone.",
            price=799.99,
            category="Smartphones",
            stock_quantity=10,
            is_active=True,
        )

        db.session.add_all([customer, samsung, iphone])
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()