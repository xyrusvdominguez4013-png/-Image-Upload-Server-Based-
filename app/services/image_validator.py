"""Upload validation: extension/MIME allow-listing, size limits, and
image-content verification via Pillow so a renamed non-image file (or a
polyglot/executable) is rejected even if its extension looks legitimate.
"""
from dataclasses import dataclass

from PIL import Image as PILImage, UnidentifiedImageError
from werkzeug.datastructures import FileStorage


@dataclass
class ValidationResult:
    ok: bool
    error: str | None = None
    extension: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None


# Map Pillow's format identifier back to a canonical MIME type, independent
# of whatever Content-Type the browser happened to send.
_PILLOW_FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}


def _extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_upload(file_storage: FileStorage, allowed_extensions: set[str],
                     allowed_mime_types: set[str], max_size_bytes: int) -> ValidationResult:
    """Run every validation rule required by the spec and return a single
    ValidationResult so routes never have to duplicate this logic.
    """
    if not file_storage or file_storage.filename == "":
        return ValidationResult(ok=False, error="No file was selected.")

    filename = file_storage.filename
    extension = _extension_of(filename)
    if extension not in allowed_extensions:
        return ValidationResult(
            ok=False,
            error=f"File type '.{extension}' is not allowed. Allowed types: "
                  f"{', '.join(sorted(allowed_extensions))}.",
        )

    # Size check without loading the whole file into memory twice.
    file_storage.stream.seek(0, 2)  # seek to end
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        return ValidationResult(ok=False, error="Uploaded file is empty.")
    if size > max_size_bytes:
        return ValidationResult(
            ok=False,
            error=f"File is {size / (1024 * 1024):.2f} MB, which exceeds the "
                  f"{max_size_bytes / (1024 * 1024):.0f} MB limit.",
        )

    # Verify the browser-supplied MIME type against the allow-list. This is
    # advisory only (clients can lie) -- the Pillow check below is the real
    # content-integrity gate.
    if file_storage.mimetype not in allowed_mime_types:
        return ValidationResult(
            ok=False,
            error=f"MIME type '{file_storage.mimetype}' is not allowed.",
        )

    # Verify actual image integrity/content with Pillow. This rejects
    # executables, corrupt files, and anything else that isn't a decodable
    # image, regardless of extension or declared MIME type.
    try:
        with PILImage.open(file_storage.stream) as img:
            img.verify()
        file_storage.stream.seek(0)
        with PILImage.open(file_storage.stream) as img:
            width, height = img.size
            detected_format = img.format
    except (UnidentifiedImageError, OSError, ValueError):
        return ValidationResult(ok=False, error="File content is not a valid image.")
    finally:
        file_storage.stream.seek(0)

    detected_mime = _PILLOW_FORMAT_TO_MIME.get(detected_format or "")
    if detected_mime is None or detected_mime not in allowed_mime_types:
        return ValidationResult(
            ok=False,
            error=f"Decoded image format '{detected_format}' is not allowed.",
        )

    return ValidationResult(
        ok=True,
        extension=extension,
        mime_type=detected_mime,
        width=width,
        height=height,
    )
