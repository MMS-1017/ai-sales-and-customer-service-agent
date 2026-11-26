import sqlalchemy as sa

from app.extensions import db
from app.models.customer import Customer
from app.models.customer_identity import CustomerChannelIdentity
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.message_attachment import MessageAttachment
from app.models.product import Product
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.knowledge import KnowledgeDocument
from app.models.media_file import MediaFile


def ensure_schema_columns() -> None:
    """Idempotently add missing columns to pre-existing tables without Alembic."""
    inspector = sa.inspect(db.engine)
    if "conversations" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("conversations")}
        if "response_mode" not in columns:
            db.session.execute(
                sa.text(
                    "ALTER TABLE conversations "
                    "ADD COLUMN response_mode VARCHAR(16) NOT NULL DEFAULT 'agent'"
                )
            )
            db.session.commit()


__all__ = [
    "Customer",
    "CustomerChannelIdentity",
    "Conversation",
    "Message",
    "MessageAttachment",
    "Product",
    "Order",
    "OrderItem",
    "KnowledgeDocument",
    "MediaFile",
    "ensure_schema_columns",
]