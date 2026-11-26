from datetime import datetime, timezone

from app.extensions import db


class CustomerChannelIdentity(db.Model):
    """Associates an external messaging channel identity with an internal Customer."""

    __tablename__ = "customer_channel_identities"
    __table_args__ = (
        db.UniqueConstraint(
            "channel",
            "channel_account_id",
            "external_user_id",
            name="uq_customer_channel_identity",
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
    external_user_id = db.Column(db.String(255), nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    identity_metadata = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    customer = db.relationship("Customer", back_populates="channel_identities")

    def __repr__(self) -> str:
        return (
            f"<CustomerChannelIdentity {self.channel}:{self.external_user_id} "
            f"-> customer={self.customer_id}>"
        )
