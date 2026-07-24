"""HTTP routes. Business logic is delegated to app/services/* so this
module stays a thin controller layer.
"""
import io
import math
import time

from flask import (
    Blueprint, current_app, flash, jsonify, redirect, render_template,
    request, send_file, url_for,
)

from app.extensions import db
from app.forms import ImageUploadForm
from app.models import Image, StorageMethod
from app.services.blob_storage import read_from_blob, save_to_blob
from app.services.comparison_service import COMPARISON_MATRIX, build_benchmark
from app.services.filesystem_storage import read_from_filesystem, save_to_filesystem
from app.services.image_validator import validate_upload
from app.services.statistics_service import build_statistics

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/upload/filesystem", methods=["GET", "POST"])
def upload_filesystem():
    form = ImageUploadForm()
    if form.validate_on_submit():
        result = validate_upload(
            form.image.data,
            current_app.config["ALLOWED_EXTENSIONS"],
            current_app.config["ALLOWED_MIME_TYPES"],
            current_app.config["MAX_CONTENT_LENGTH"],
        )
        if not result.ok:
            flash(result.error, "danger")
        else:
            try:
                image = save_to_filesystem(
                    form.image.data,
                    extension=result.extension,
                    mime_type=result.mime_type,
                    upload_folder=current_app.config["UPLOAD_FOLDER"],
                )
                current_app.logger.info(
                    "Saved filesystem image id=%s original=%s size=%s",
                    image.id, image.original_filename, image.filesize,
                )
                flash(
                    f"'{image.original_filename}' uploaded successfully to the file system.",
                    "success",
                )
                return redirect(url_for("main.gallery"))
            except OSError as exc:
                current_app.logger.exception("Filesystem upload failed: %s", exc)
                flash("Could not save the file to disk. Please try again.", "danger")
    return render_template("filesystem_upload.html", form=form)


@main_bp.route("/upload/blob", methods=["GET", "POST"])
def upload_blob():
    form = ImageUploadForm()
    if form.validate_on_submit():
        result = validate_upload(
            form.image.data,
            current_app.config["ALLOWED_EXTENSIONS"],
            current_app.config["ALLOWED_MIME_TYPES"],
            current_app.config["MAX_CONTENT_LENGTH"],
        )
        if not result.ok:
            flash(result.error, "danger")
        else:
            try:
                image = save_to_blob(
                    form.image.data,
                    extension=result.extension,
                    mime_type=result.mime_type,
                )
                current_app.logger.info(
                    "Saved BLOB image id=%s original=%s size=%s",
                    image.id, image.original_filename, image.filesize,
                )
                flash(
                    f"'{image.original_filename}' uploaded successfully to the database.",
                    "success",
                )
                return redirect(url_for("main.gallery"))
            except Exception as exc:  # noqa: BLE001 - surfaced to the user, logged for us
                current_app.logger.exception("BLOB upload failed: %s", exc)
                db.session.rollback()
                flash("Could not save the file to the database. Please try again.", "danger")
    return render_template("blob_upload.html", form=form)


@main_bp.route("/gallery")
def gallery():
    storage_filter = request.args.get("storage", "all")
    search = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    page_size = current_app.config["GALLERY_PAGE_SIZE"]

    query = Image.query
    if storage_filter in StorageMethod.CHOICES:
        query = query.filter(Image.storage_method == storage_filter)
    if search:
        query = query.filter(Image.original_filename.ilike(f"%{search}%"))

    query = query.order_by(Image.upload_time.desc())
    total = query.count()
    images = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = max(1, math.ceil(total / page_size))

    return render_template(
        "gallery.html",
        images=images,
        storage_filter=storage_filter,
        search=search,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@main_bp.route("/image/blob/<int:image_id>")
def stream_blob_image(image_id):
    image = Image.query.get_or_404(image_id)
    if image.storage_method != StorageMethod.BLOB or image.blob is None:
        return jsonify(error="Image is not stored as a BLOB."), 404

    data, duration_ms = read_from_blob(image)
    image.last_retrieval_duration_ms = duration_ms
    db.session.commit()

    return send_file(
        io.BytesIO(data),
        mimetype=image.mime_type,
        download_name=image.original_filename,
        as_attachment=False,
    )


@main_bp.route("/image/filesystem/<int:image_id>")
def stream_filesystem_image(image_id):
    """Serve a filesystem-stored image and record retrieval latency.

    Not part of the original route table but required so the Gallery can
    render filesystem thumbnails the same way it streams BLOB images.
    """
    image = Image.query.get_or_404(image_id)
    if image.storage_method != StorageMethod.FILESYSTEM:
        return jsonify(error="Image is not stored on the file system."), 404

    data, duration_ms = read_from_filesystem(image, current_app.config["UPLOAD_FOLDER"])
    image.last_retrieval_duration_ms = duration_ms
    db.session.commit()

    return send_file(
        io.BytesIO(data),
        mimetype=image.mime_type,
        download_name=image.original_filename,
        as_attachment=False,
    )


@main_bp.route("/comparison")
def comparison():
    stats = build_statistics(current_app.config["UPLOAD_FOLDER"])
    benchmark = build_benchmark(stats)
    return render_template(
        "comparison.html", matrix=COMPARISON_MATRIX, benchmark=benchmark, stats=stats
    )


@main_bp.route("/statistics")
def statistics():
    stats = build_statistics(current_app.config["UPLOAD_FOLDER"])
    return render_template("statistics.html", stats=stats)
