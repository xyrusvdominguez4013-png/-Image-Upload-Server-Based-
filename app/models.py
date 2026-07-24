"""SQLAlchemy models for the image storage demo.

Two storage strategies share a single ``images`` metadata table:

* ``filesystem`` -- the file lives on disk, ``Image.filepath`` points to it.
* ``blob``       -- the raw bytes live in the related ``ImageBlob`` row.
"""
from datetime import datetime, timezone

from app.extensions import db

# SQLite only auto-increments a primary key declared as plain "INTEGER
# PRIMARY KEY" -- BIGINT (used so MySQL gets a real BIGINT AUTO_INCREMENT
# column) doesn't get that treatment there, so id generation would silently
# fail on SQLite without this per-dialect variant.
BigIntPK = db.BigInteger().with_variant(db.Integer, "sqlite")


class StorageMethod:
    FILESYSTEM = "filesystem"
    BLOB = "blob"
    CHOICES = (FILESYSTEM, BLOB)


class Image(db.Model):
    """Metadata common to every uploaded image, regardless of storage method."""

    __tablename__ = "images"

    id = db.Column(BigIntPK, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    extension = db.Column(db.String(20), nullable=False)
    filesize = db.Column(db.BigInteger, nullable=False)
    storage_method = db.Column(
        db.Enum(*StorageMethod.CHOICES, name="storage_method_enum"),
        nullable=False,
        index=True,
    )
    filepath = db.Column(db.String(500), nullable=True)
    upload_time = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Performance metrics (see docs/ARCHITECTURE.md "Performance Metrics")
    upload_duration_ms = db.Column(db.Float, nullable=True)
    last_retrieval_duration_ms = db.Column(db.Float, nullable=True)

    # passive_deletes is intentionally NOT set: that would rely on the
    # database's own ON DELETE CASCADE, which MySQL enforces but SQLite
    # does not by default -- it would silently orphan image_blobs rows in
    # SQLite (dev) while working fine in MySQL (prod). Letting SQLAlchemy's
    # ORM issue the child DELETE itself works correctly on both.
    blob = db.relationship(
        "ImageBlob",
        backref="image",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):  # pragma: no cover - debugging helper
        return f"<Image id={self.id} storage={self.storage_method} name={self.original_filename!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "extension": self.extension,
            "filesize": self.filesize,
            "storage_method": self.storage_method,
            "filepath": self.filepath,
            "upload_time": self.upload_time.isoformat() if self.upload_time else None,
        }


class ImageBlob(db.Model):
    """Binary payload for images stored directly in the database."""

    __tablename__ = "image_blobs"

    id = db.Column(BigIntPK, primary_key=True)
    image_id = db.Column(
        BigIntPK,
        db.ForeignKey("images.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    image_data = db.Column(db.LargeBinary(length=(2**32) - 1), nullable=False)  # LONGBLOB

    def __repr__(self):  # pragma: no cover - debugging helper
        return f"<ImageBlob id={self.id} image_id={self.image_id} bytes={len(self.image_data or b'')}>"
