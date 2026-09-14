from flask import Blueprint, render_template, request, redirect, url_for

from app.extensions import db
from app.models import Customer, Order, Product, KnowledgeDocument


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/")
def dashboard():
    stats = {
        "products": Product.query.count(),
        "orders": Order.query.count(),
        "customers": Customer.query.count(),
        "knowledge_documents": KnowledgeDocument.query.count(),
    }

    return render_template("dashboard.html", stats=stats)


# =========================
# Products
# =========================

@admin_bp.get("/products")
def products():
    products = Product.query.order_by(Product.id).all()

    return render_template(
        "products.html",
        products=products,
    )


@admin_bp.post("/products/create")
def create_product():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "").strip()
    stock_quantity = request.form.get("stock_quantity", "").strip()

    if not all([name, description, category, price, stock_quantity]):
        return "All fields are required.", 400

    try:
        product = Product(
            name=name,
            description=description,
            category=category,
            price=price,
            stock_quantity=int(stock_quantity),
            is_active=True,
        )

        db.session.add(product)
        db.session.commit()

    except Exception:
        db.session.rollback()
        return "Failed to create product.", 400

    return redirect(url_for("admin.products"))


@admin_bp.post("/products/<int:product_id>/edit")
def edit_product(product_id):
    product = db.session.get(Product, product_id)

    if not product:
        return "Product not found.", 404

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "").strip()
    stock_quantity = request.form.get("stock_quantity", "").strip()

    if not all([name, description, category, price, stock_quantity]):
        return "All fields are required.", 400

    try:
        product.name = name
        product.description = description
        product.category = category
        product.price = price
        product.stock_quantity = int(stock_quantity)

        db.session.commit()

    except Exception:
        db.session.rollback()
        return "Failed to update product.", 400

    return redirect(url_for("admin.products"))


@admin_bp.post("/products/<int:product_id>/deactivate")
def deactivate_product(product_id):
    product = db.session.get(Product, product_id)

    if not product:
        return "Product not found.", 404

    product.is_active = False
    db.session.commit()

    return redirect(url_for("admin.products"))