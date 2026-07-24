"""WSGI entry point loaded by mod_wsgi. Keep this file minimal -- all real
application setup happens in the app factory (app/__init__.py).
"""
import sys
import os

PROJECT_ROOT = "/var/www/image-storage-demo"
VENV_SITE_PACKAGES = "/var/www/image-storage-demo/venv/lib/python3.12/site-packages"

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_SITE_PACKAGES)

# Load environment variables from .env (python-dotenv) so DATABASE_URL,
# SECRET_KEY, etc. are available to the app the same way they are in dev.
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app import create_app

application = create_app(os.environ.get("FLASK_ENV", "production"))
