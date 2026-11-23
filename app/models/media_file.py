from datetime import datetime, timezone
from app.extensions import db


class MediaFile(db.Model):
    __tablename__ = "media_files"

    id = db.Column(db.Integer, primary_key=True)
    
    file_name = db.Column(db.String(255), nullable=False)
    extension = db.Column(db.String(20), nullable=False)
    file_path = db.Column(db.String(500), nullable=False, unique=True)

    content = db.Column(db.LargeBinary, nullable=False)
    media_type = db.Column(db.String(20), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(30), nullable=False) 

    customer_id = db.Column(db.Integer, 
                            db.ForeignKey("customers.id"), 
                            nullable=False, 
                            index=True
                    )
    created_at = db.Column(db.DateTime(timezone=True),
                            default=lambda: datetime.now(timezone.utc),
                            nullable=False
                    )
    customer = db.relationship("Customer", 
                                backref=db.backref("media_files", lazy=True)
                            )

    def __repr__(self):
        return f"<MediaFile {self.id}: {self.file_name}>"
