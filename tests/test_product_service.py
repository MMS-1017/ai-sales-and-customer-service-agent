from app.services.product_service import ProductService


def test_get_product(app):
    with app.app_context():
        product = ProductService.get_product(1)

        assert product is not None
        assert product.name == "Samsung Galaxy S24"


def test_search_products(app):
    with app.app_context():
        products = ProductService.search_products(query="Samsung")

        assert len(products) == 1
        assert products[0].name == "Samsung Galaxy S24"


def test_check_product_availability(app):
    with app.app_context():
        result = ProductService.check_availability(
            product_id=1,
            quantity=2,
        )

        assert result["success"] is True
        assert result["in_stock"] is True
        assert result["requested_quantity"] == 2
        assert result["available_quantity"] == 15