"""Development entry point. Production uses the WSGI callable in
deployment/apache/image-storage-demo.wsgi via mod_wsgi instead of this file.
"""
import os

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=app.config["DEBUG"])
