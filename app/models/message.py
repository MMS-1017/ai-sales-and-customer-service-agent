from datetime import datetime, timezone

from app.extensions import db


class Message(db.Model):
    """Unified persisted inbound or outbound message within a Conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        db.Index(
            "uq_inbound_external_msg_id",
            "channel",
            "channel_account_id",
            "external_message_id",
            unique=True,
            postgresql_where=db.text("external_message_id IS NOT NULL AND direction = 'inbound'"),
            sqlite_where=db.text("external_message_id IS NOT NULL AND direction = 'inbound'"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    internal_id = db.Column(db.String(64), unique=True, nullable=False)
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel = db.Column(db.String(32), nullable=False, index=True)
    channel_account_id = db.Column(db.String(128), nullable=False, default="")
    direction = db.Column(db.String(16), nullable=False)  # inbound | outbound
    role = db.Column(db.String(16), nullable=False)  # customer | assistant | system
    external_message_id = db.Column(db.String(255), nullable=True, index=True)
    message_type = db.Column(db.String(32), nullable=False, default="text")
    content = db.Column(db.Text, nullable=False, default="")
    delivery_status = db.Column(db.String(32), nullable=False, default="received")
    provider_timestamp = db.Column(db.DateTime(timezone=True), nullable=True)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    conversation = db.relationship("Conversation", back_populates="messages")
    customer = db.relationship("Customer", backref=db.backref("messages", lazy=True))
    attachments = db.relationship(
        "MessageAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Message {self.id} {self.direction} {self.channel} "
            f"conv={self.conversation_id}>"
        )
