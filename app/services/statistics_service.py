"""Aggregate metrics for the Statistics dashboard."""
import os
from dataclasses import dataclass, field

from sqlalchemy import func

from app.extensions import db
from app.models import Image, ImageBlob, StorageMethod


@dataclass
class Statistics:
    total_images: int = 0
    filesystem_count: int = 0
    blob_count: int = 0
    upload_folder_size_bytes: int = 0
    blob_storage_size_bytes: int = 0
    avg_upload_duration_ms: float | None = None
    avg_retrieval_duration_ms: float | None = None
    largest_image: dict | None = None
    smallest_image: dict | None = None
    avg_upload_duration_by_method: dict = field(default_factory=dict)


def _folder_size_bytes(folder: str) -> int:
    total = 0
    if not os.path.isdir(folder):
        return 0
    for entry in os.scandir(folder):
        if entry.is_file():
            total += entry.stat().st_size
    return total


def build_statistics(upload_folder: str) -> Statistics:
    stats = Statistics()

    stats.total_images = db.session.query(func.count(Image.id)).scalar() or 0
    stats.filesystem_count = (
        db.session.query(func.count(Image.id))
        .filter(Image.storage_method == StorageMethod.FILESYSTEM)
        .scalar()
        or 0
    )
    stats.blob_count = (
        db.session.query(func.count(Image.id))
        .filter(Image.storage_method == StorageMethod.BLOB)
        .scalar()
        or 0
    )

    stats.upload_folder_size_bytes = _folder_size_bytes(upload_folder)
    stats.blob_storage_size_bytes = (
        db.session.query(func.coalesce(func.sum(func.length(ImageBlob.image_data)), 0)).scalar()
        or 0
    )

    stats.avg_upload_duration_ms = db.session.query(
        func.avg(Image.upload_duration_ms)
    ).scalar()
    stats.avg_retrieval_duration_ms = db.session.query(
        func.avg(Image.last_retrieval_duration_ms)
    ).scalar()

    for method in StorageMethod.CHOICES:
        avg = (
            db.session.query(func.avg(Image.upload_duration_ms))
            .filter(Image.storage_method == method)
            .scalar()
        )
        stats.avg_upload_duration_by_method[method] = avg

    largest = db.session.query(Image).order_by(Image.filesize.desc()).first()
    smallest = db.session.query(Image).order_by(Image.filesize.asc()).first()
    stats.largest_image = largest.to_dict() if largest else None
    stats.smallest_image = smallest.to_dict() if smallest else None

    return stats
