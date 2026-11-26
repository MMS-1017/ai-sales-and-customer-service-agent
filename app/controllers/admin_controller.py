from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, render_template, request, redirect, url_for
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import Conversation, Customer, KnowledgeDocument, Message, Order, Product
from app.services import CustomerIdentityService, KnowledgeService
from app.services.identity_service import CustomerNotFoundError, IdentityConflictError

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
def require_admin_auth():
    if current_app.config.get("TESTING") and not current_app.config.get("ADMIN_AUTH_STRICT"):
        return None
    if not current_app.config.get("ADMIN_AUTH_ENABLED", True):
        return None
    auth = request.authorization
    admin_user = current_app.config.get("ADMIN_USERNAME", "admin")
    admin_pass = current_app.config.get("ADMIN_PASSWORD", "admin123")
    if not auth or auth.username != admin_user or auth.password != admin_pass:
        return (
            "Unauthorized: Admin login required",
            401,
            {"WWW-Authenticate": 'Basic realm="Admin Access Required"'},
        )


@admin_bp.get("/")
def dashboard():
    stats = {
        "products": Product.query.count(),
        "orders": Order.query.count(),
        "customers": Customer.query.count(),
        "conversations": Conversation.query.count(),
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


@admin_bp.post("/customers/link-identity")
def link_customer_identity():
    raw_customer_id = request.form.get("customer_id", "").strip()
    channel = request.form.get("channel", "").strip()
    external_user_id = request.form.get("external_user_id", "").strip()
    channel_account_id = request.form.get("channel_account_id", "").strip()

    try:
        customer_id = int(raw_customer_id)
    except ValueError:
        return "Customer ID must be an integer.", 400

    try:
        CustomerIdentityService.link_identity(
            customer_id=customer_id,
            channel=channel,
            external_user_id=external_user_id,
            channel_account_id=channel_account_id,
            verified=True,
        )
    except CustomerNotFoundError as exc:
        return str(exc), 404
    except (IdentityConflictError, ValueError) as exc:
        return str(exc), 400

    return redirect(url_for("admin.customers"))


# =========================
# Omnichannel Conversations
# =========================

@admin_bp.get("/conversations")
def conversations():
    selected_channel = request.args.get("channel", "").strip().lower()
    raw_customer_id = request.args.get("customer_id", "").strip()
    search_query = request.args.get("q", "").strip()

    query = Conversation.query.options(
        joinedload(Conversation.customer),
        selectinload(Conversation.messages),
    )

    if selected_channel:
        query = query.filter(Conversation.channel == selected_channel)

    selected_customer_id = None
    if raw_customer_id:
        try:
            selected_customer_id = int(raw_customer_id)
            query = query.filter(Conversation.customer_id == selected_customer_id)
        except ValueError:
            selected_customer_id = None

    if search_query:
        like_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Conversation.external_conversation_id.ilike(like_pattern),
                Conversation.customer.has(
                    or_(
                        Customer.name.ilike(like_pattern),
                        Customer.email.ilike(like_pattern),
                    )
                ),
                Conversation.messages.any(Message.content.ilike(like_pattern)),
            )
        )

    convs = (
        query
        .order_by(Conversation.last_message_at.desc(), Conversation.id.desc())
        .limit(200)
        .all()
    )

    db_channels = {
        row[0] for row in db.session.query(Conversation.channel).distinct().all() if row[0]
    }
    channels = sorted({"web_chat", "whatsapp", "facebook"} | db_channels)

    return render_template(
        "conversations.html",
        conversations=convs,
        channels=channels,
        selected_channel=selected_channel,
        selected_customer_id=selected_customer_id,
        search_query=search_query,
    )


@admin_bp.get("/conversations/<int:conversation_id>")
def conversation_detail(conversation_id: int):
    conv = (
        Conversation.query.options(
            joinedload(Conversation.customer).selectinload(Customer.channel_identities),
            selectinload(Conversation.messages).selectinload(Message.attachments),
        )
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not conv:
        return "Conversation not found.", 404

    other_conversations = (
        Conversation.query.options(selectinload(Conversation.messages))
        .filter(
            Conversation.customer_id == conv.customer_id,
            Conversation.id != conv.id,
        )
        .order_by(Conversation.last_message_at.desc(), Conversation.id.desc())
        .all()
    )

    return render_template(
        "conversation_detail.html",
        conversation=conv,
        other_conversations=other_conversations,
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