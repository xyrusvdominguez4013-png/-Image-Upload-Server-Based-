"""File-system storage strategy: bytes live on disk under UPLOAD_FOLDER,
only metadata (including the relative filepath) is persisted in MySQL.
"""
import os
import time
import uuid

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Image, StorageMethod


def save_to_filesystem(file_storage: FileStorage, *, extension: str, mime_type: str,
                        upload_folder: str) -> Image:
    """Write the upload to disk under a UUID filename and persist metadata.

    Returns the newly created Image row (already committed).
    """
    start = time.perf_counter()

    original_filename = secure_filename(file_storage.filename)
    unique_filename = f"{uuid.uuid4().hex}.{extension}"
    os.makedirs(upload_folder, exist_ok=True)
    destination = os.path.join(upload_folder, unique_filename)

    file_storage.stream.seek(0)
    file_storage.save(destination)
    filesize = os.path.getsize(destination)

    duration_ms = (time.perf_counter() - start) * 1000

    image = Image(
        filename=unique_filename,
        original_filename=original_filename,
        mime_type=mime_type,
        extension=extension,
        filesize=filesize,
        storage_method=StorageMethod.FILESYSTEM,
        filepath=os.path.join("uploads", unique_filename).replace("\\", "/"),
        upload_duration_ms=duration_ms,
    )
    db.session.add(image)
    db.session.commit()
    return image


def delete_from_filesystem(image: Image, upload_folder: str) -> None:
    if not image.filepath:
        return
    absolute_path = os.path.join(upload_folder, os.path.basename(image.filepath))
    if os.path.exists(absolute_path):
        os.remove(absolute_path)
    db.session.delete(image)
    db.session.commit()


def read_from_filesystem(image: Image, upload_folder: str) -> tuple[bytes, float]:
    """Return (bytes, retrieval_duration_ms) for the given filesystem image."""
    start = time.perf_counter()
    absolute_path = os.path.join(upload_folder, os.path.basename(image.filepath))
    with open(absolute_path, "rb") as fh:
        data = fh.read()
    duration_ms = (time.perf_counter() - start) * 1000
    return data, duration_ms
