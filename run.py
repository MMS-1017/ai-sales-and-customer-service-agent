import os
from app import create_app

# Flask App
app = create_app()

if __name__ == "__main__":
    
    app.run(debug=True, use_reloader=False)
    # use_reloader=False to prevent watchdog on Windows from detecting false
    # file change events when transformers / PyTorch models are loaded.