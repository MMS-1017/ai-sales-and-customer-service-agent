from datetime import datetime, timezone

from app.extensions import db


class MessageAttachment(db.Model):
    """Attachment metadata associated with a persisted Message and optional MediaFile."""

    __tablename__ = "message_attachments"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.Integer,
        db.ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_file_id = db.Column(
        db.Integer,
        db.ForeignKey("media_files.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    media_type = db.Column(db.String(32), nullable=False)
    file_name = db.Column(db.String(255), nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    external_url = db.Column(db.String(1000), nullable=True)
    extracted_text = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    message = db.relationship("Message", back_populates="attachments")
    media_file = db.relationship("MediaFile", backref=db.backref("message_attachments", lazy=True))

    def __repr__(self) -> str:
        return f"<MessageAttachment {self.id} {self.media_type} msg={self.message_id}>"
