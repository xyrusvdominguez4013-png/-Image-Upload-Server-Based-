"""Database BLOB storage strategy: raw bytes live in MySQL's LONGBLOB
column (image_blobs.image_data), only metadata is duplicated elsewhere.
"""
import time
import uuid

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Image, ImageBlob, StorageMethod


def save_to_blob(file_storage: FileStorage, *, extension: str, mime_type: str) -> Image:
    """Read the upload's binary content and store it directly in MySQL.

    Returns the newly created Image row (already committed), with its
    related ImageBlob accessible via ``image.blob``.
    """
    start = time.perf_counter()

    original_filename = secure_filename(file_storage.filename)
    unique_filename = f"{uuid.uuid4().hex}.{extension}"

    file_storage.stream.seek(0)
    data = file_storage.stream.read()
    filesize = len(data)

    image = Image(
        filename=unique_filename,
        original_filename=original_filename,
        mime_type=mime_type,
        extension=extension,
        filesize=filesize,
        storage_method=StorageMethod.BLOB,
        filepath=None,
    )
    image.blob = ImageBlob(image_data=data)

    duration_ms = (time.perf_counter() - start) * 1000
    image.upload_duration_ms = duration_ms

    db.session.add(image)
    db.session.commit()
    return image


def read_from_blob(image: Image) -> tuple[bytes, float]:
    """Return (bytes, retrieval_duration_ms) for the given BLOB image."""
    start = time.perf_counter()
    data = image.blob.image_data
    duration_ms = (time.perf_counter() - start) * 1000
    return data, duration_ms


def delete_blob(image: Image) -> None:
    db.session.delete(image)  # cascades to ImageBlob via relationship
    db.session.commit()
