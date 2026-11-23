import os
from app import create_app

# Flask App
app = create_app()


if __name__ == "__main__":
    
    # Disable the Werkzeug reloader (use_reloader=False) to prevent watchdog on Windows
    # from detecting false file change events when transformers / PyTorch models are loaded.
    use_reloader = os.getenv("FLASK_USE_RELOADER", "false").lower() in ("true", "1")
    app.run(debug=True, use_reloader=use_reloader)
