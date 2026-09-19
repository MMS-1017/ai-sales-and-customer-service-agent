import os

import pytest

from app import create_app
from app.extensions import db
from app.models import Customer, Product

from unittest.mock import MagicMock


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


class FakeStructuredLLM:
    def invoke(self, prompt):
        from app.agent.nodes import ProductRequest

        prompt_lower = prompt.lower()

        quantity = None

        if "buy 2" in prompt_lower:
            quantity = 2
        elif "buy 1" in prompt_lower:
            quantity = 1

        return ProductRequest(
            product_name="Samsung Galaxy S24",
            quantity=quantity,
        )


class FakeLLM:
    def invoke(self, prompt):
        response = MagicMock()

        prompt_lower = prompt.lower()

        # Intent classification
        if "intent" in prompt_lower:
            if "buy 2" in prompt_lower or "buy 1" in prompt_lower:
                response.content = "create_order"
            elif "is it available" in prompt_lower:
                response.content = "availability_check"
            elif "how much" in prompt_lower:
                response.content = "product_question"
            else:
                response.content = "unknown"

            return response

        # Final response generation
        if "order" in prompt_lower and "authoritative backend tool result" in prompt_lower:
            response.content = (
                "Your order has been successfully placed."
            )
        else:
            response.content = (
                "The Samsung Galaxy S24 is currently priced at $699.99."
            )

        return response

    def with_structured_output(self, schema):
        return FakeStructuredLLM()


@pytest.fixture
def mock_llm(monkeypatch):
    fake_llm = FakeLLM()

    monkeypatch.setattr(
        "app.agent.nodes.get_llm",
        lambda: fake_llm,
    )

    return fake_llm