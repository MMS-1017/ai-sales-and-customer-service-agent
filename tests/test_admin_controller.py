def test_admin_dashboard(client):
    response = client.get("/admin/")

    assert response.status_code == 200


def test_admin_products_page(client):
    response = client.get("/admin/products")

    assert response.status_code == 200


def test_admin_orders_page(client):
    response = client.get("/admin/orders")

    assert response.status_code == 200


def test_admin_customers_page(client):
    response = client.get("/admin/customers")

    assert response.status_code == 200


def test_admin_knowledge_page(client):
    response = client.get("/admin/knowledge")

    assert response.status_code == 200