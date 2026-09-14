from flask import Blueprint, render_template

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

    return render_template(
        "dashboard.html",
        stats=stats,
    )