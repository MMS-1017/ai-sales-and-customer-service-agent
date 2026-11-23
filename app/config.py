import os
from dotenv import load_dotenv
load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CHROMA_PATH = os.path.abspath(os.getenv("CHROMA_PATH"))

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL")
    GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL")
    GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL")

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

    FACEBOOK_VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN")
    FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
    FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
    FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
    FACEBOOK_GRAPH_VERSION = os.getenv("FACEBOOK_GRAPH_VERSION", "v24.0")

    WAHA_BASE_URL = os.getenv("WAHA_BASE_URL")
    WAHA_API_KEY = os.getenv("WAHA_API_KEY")
    WAHA_SESSION = os.getenv("WAHA_SESSION", "default")
    WAHA_WEBHOOK_SECRET = os.getenv("WAHA_WEBHOOK_SECRET")

    # Media storage and processing
    MEDIA_STORAGE_DIR = os.getenv(
        "MEDIA_STORAGE_DIR",
        os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "uploads", "media"),
    )
    

    MEDIA_MAX_IMAGE_MB = int(os.getenv("MEDIA_MAX_IMAGE_MB", "10"))
    MEDIA_MAX_AUDIO_MB = int(os.getenv("MEDIA_MAX_AUDIO_MB", "25"))

    # Admin panel credentials and authentication
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
    ADMIN_AUTH_ENABLED = os.getenv("ADMIN_AUTH_ENABLED", "true").lower() in ("true", "1", "yes")

    # Timezone used for displaying timestamps in the admin UI.
    # Set to any IANA timezone string, e.g. "Asia/Riyadh", "Europe/Istanbul".
    DISPLAY_TIMEZONE = os.getenv("DISPLAY_TIMEZONE")
