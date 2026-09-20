from flask import Flask, redirect
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import timezone as _utc

from app.config import Config
from app.extensions import db
from app.models import Customer, Product, Order, OrderItem, KnowledgeDocument
from app.controllers.chat_controller import chat_bp
from app.controllers.admin_controller import admin_bp
from app.controllers.facebook_controller import facebook_bp


def create_app(test_config=None):
    app = Flask(
        __name__,
        template_folder="views/templates",
        static_folder="views/static",
    )

    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(facebook_bp)

    db.init_app(app)

    # ------------------------------------------------------------------
    # Jinja2 filter: {{ dt | localtime }}
    # Converts a UTC-aware datetime to the configured DISPLAY_TIMEZONE.
    # Registered before db.create_all() so a DB error can't skip it.
    # ------------------------------------------------------------------
    try:
        _tz = ZoneInfo(app.config.get("DISPLAY_TIMEZONE", "UTC"))
    except (ZoneInfoNotFoundError, KeyError):
        _tz = ZoneInfo("UTC")

    def localtime_filter(dt, fmt="%Y-%m-%d %H:%M"):
        if dt is None:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_utc.utc)
        return dt.astimezone(_tz).strftime(fmt)

    app.jinja_env.filters["localtime"] = localtime_filter

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