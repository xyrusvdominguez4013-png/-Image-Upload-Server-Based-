"""Application factory for the Image Storage Demo Flask app."""
import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask

from config import config_by_name
from app.extensions import db, migrate, csrf


def create_app(config_name: str | None = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    _configure_logging(app)

    from app.routes import main_bp
    app.register_blueprint(main_bp)

    from app import models  # noqa: F401  (ensure models are registered with SQLAlchemy)

    @app.errorhandler(413)
    def request_entity_too_large(_error):
        from flask import jsonify, request
        if request.accept_mimetypes.accept_json:
            return jsonify(error="File exceeds the 10 MB upload limit."), 413
        from flask import flash, redirect, url_for
        flash("File exceeds the 10 MB upload limit.", "danger")
        return redirect(url_for("main.index")), 413

    @app.errorhandler(404)
    def not_found(_error):
        from flask import render_template
        return render_template("base.html", content_title="Not Found"), 404

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Unhandled server error: %s", error)
        from flask import render_template
        return render_template("base.html", content_title="Server Error"), 500

    return app


def _configure_logging(app: Flask) -> None:
    if app.testing:
        return
    log_level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"), logging.INFO)
    handler = RotatingFileHandler(
        app.config["LOG_FILE"], maxBytes=1_000_000, backupCount=3
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )
    )
    handler.setLevel(log_level)
    app.logger.addHandler(handler)
    app.logger.setLevel(log_level)
