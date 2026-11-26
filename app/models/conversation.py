from datetime import datetime, timezone

from app.extensions import db


class Conversation(db.Model):
    """Persistent channel-scoped conversation thread linked to an internal Customer."""

    __tablename__ = "conversations"
    __table_args__ = (
        db.UniqueConstraint(
            "channel",
            "channel_account_id",
            "external_conversation_id",
            name="uq_conversation_channel_external_id",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel = db.Column(db.String(32), nullable=False, index=True)
    channel_account_id = db.Column(db.String(128), nullable=False, default="")
    external_conversation_id = db.Column(db.String(255), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="open", index=True)
    response_mode = db.Column(db.String(16), nullable=False, default="agent", index=True)  # agent | admin
    summary = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    started_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_message_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    customer = db.relationship("Customer", back_populates="conversations")
    messages = db.relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation {self.id} {self.channel}:{self.external_conversation_id} "
            f"customer={self.customer_id}>"
        )
