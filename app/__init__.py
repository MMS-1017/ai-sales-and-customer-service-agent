from flask import Flask, redirect
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import timezone as _utc

from app.config import Config
from app.extensions import db
from app.models import (
    Customer,
    CustomerChannelIdentity,
    Conversation,
    Message,
    MessageAttachment,
    Product,
    Order,
    OrderItem,
    KnowledgeDocument,
    MediaFile,
)

# Blueprints responsible for routes
from app.controllers.chat_controller import chat_bp
from app.controllers.admin_controller import admin_bp
from app.controllers.facebook_controller import facebook_bp
from app.controllers.whatsapp_controller import whatsapp_bp
from app.controllers.media_controller import media_bp
from app.channels.dispatcher import omnichannel_bp


def create_app(test_config=None):
    app = Flask(
        __name__,
        template_folder="views/templates",
        static_folder="views/static",
    )

    app.config.from_object(Config)
    app.config.setdefault("MAX_CONTENT_LENGTH", 30 * 1024 * 1024)

    if test_config:
        app.config.update(test_config)

    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(facebook_bp)
    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(omnichannel_bp)

    # Connect to database through SQLAlchemy
    db.init_app(app)
    
    # specify time zone to display history
    try:
        _tz = ZoneInfo(app.config.get("DISPLAY_TIMEZONE", "UTC"))
    except (ZoneInfoNotFoundError, KeyError):
        _tz = ZoneInfo("UTC")

    # Create and register a timezone function as a jinja filter to use it in HTML
    def localtime_filter(dt, fmt="%Y-%m-%d %H:%M"):
        if dt is None:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_utc.utc)
        return dt.astimezone(_tz).strftime(fmt)
    
    app.jinja_env.filters["localtime"] = localtime_filter
    
    # Create database tables if not existed
    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:
            print(f"[WARNING] db.create_all() failed: {exc}")

    @app.get("/")
    def index():
        return redirect("/chat")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app