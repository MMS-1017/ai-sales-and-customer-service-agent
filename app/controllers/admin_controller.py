from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for

from app.extensions import db
from app.models import Customer, Order, Product, KnowledgeDocument
from app.services import KnowledgeService

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
        price_value = Decimal(price)
        stock_value = int(stock_quantity)
    except (InvalidOperation, ValueError):
        return "Price must be a valid number and stock must be a valid integer.", 400

    if price_value < 0:
        return "Price cannot be negative.", 400

    if stock_value < 0:
        return "Stock quantity cannot be negative.", 400

    try:
        product = Product(
            name=name,
            description=description,
            category=category,
            price=price_value,
            stock_quantity=stock_value,
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
        price_value = Decimal(price)
        stock_value = int(stock_quantity)
    except (InvalidOperation, ValueError):
        return "Price must be a valid number and stock must be a valid integer.", 400

    if price_value < 0:
        return "Price cannot be negative.", 400

    if stock_value < 0:
        return "Stock quantity cannot be negative.", 400

    try:
        product.name = name
        product.description = description
        product.category = category
        product.price = price_value
        product.stock_quantity = stock_value

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

# =========================
# Orders
# =========================

@admin_bp.get("/orders")
def orders():
    orders = (
        Order.query
        .order_by(Order.created_at.desc())
        .all()
    )

    return render_template(
        "orders.html",
        orders=orders,
    )
    
# =========================
# Customers
# =========================

@admin_bp.get("/customers")
def customers():
    customers = (
        Customer.query
        .order_by(Customer.created_at.desc())
        .all()
    )

    return render_template(
        "customers.html",
        customers=customers,
    )

# =========================
# Knowledge Documents
# =========================

@admin_bp.get("/knowledge")
def knowledge():

    documents = KnowledgeService.list_documents()
    return render_template("knowledge.html", documents=documents)


@admin_bp.post("/knowledge/create")
def create_knowledge():
    
    title = request.form.get("title", "")
    content = request.form.get("content", "")
    category = request.form.get("category", "")
    source = request.form.get("source", "")

    result = KnowledgeService.create_document(
        title=title,
        content=content,
        category=category,
        source=source,
    )

    if not result["success"]:
        return result["error"], 400

    return redirect(url_for("admin.knowledge"))


@admin_bp.post("/knowledge/<int:document_id>/edit")
def edit_knowledge(document_id):

    title = request.form.get("title", "")
    content = request.form.get("content", "")
    category = request.form.get("category", "")
    source = request.form.get("source", "")

    result = KnowledgeService.update_document(
        document_id=document_id,
        title=title,
        content=content,
        category=category,
        source=source,
    )

    if not result["success"]:
        return result["error"], 400

    return redirect(url_for("admin.knowledge"))


@admin_bp.post("/knowledge/<int:document_id>/delete")
def delete_knowledge(document_id):

    result = KnowledgeService.delete_document(document_id)

    if not result["success"]:
        return result["error"], 404

    return redirect(url_for("admin.knowledge"))