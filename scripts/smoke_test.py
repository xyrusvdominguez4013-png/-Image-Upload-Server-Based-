"""End-to-end smoke test for the Image Storage Demo.

Exercises the real HTTP routes through Flask's test client -- CSRF token
included -- rather than calling service functions directly, so it catches
wiring bugs (routing, CSRF, template rendering) that a unit test would
miss. Intended to run against a disposable database (see install.sh,
which points DATABASE_URL/UPLOAD_FOLDER at throwaway locations before
invoking this script and tears them down afterward).

Exit code 0 on success, 1 on any failed check.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.models import Image  # noqa: E402

CSRF_RE = re.compile(rb'name="csrf_token"[^>]*value="([^"]+)"')


class SmokeTestFailure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeTestFailure(message)


def extract_csrf(html: bytes) -> str:
    match = CSRF_RE.search(html)
    check(match is not None, "Could not find a CSRF token in the response HTML")
    return match.group(1).decode()


def tiny_png_bytes(color: tuple[int, int, int]) -> bytes:
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (16, 16), color=color).save(buf, format="PNG")
    return buf.getvalue()


def run() -> None:
    app = create_app(os.environ.get("SMOKE_TEST_ENV", "development"))
    fs_bytes = tiny_png_bytes((255, 0, 0))
    blob_bytes = tiny_png_bytes((0, 0, 255))

    with app.test_client() as client:
        resp = client.get("/")
        check(resp.status_code == 200, f"GET / -> {resp.status_code}")

        # --- File system upload -------------------------------------------
        resp = client.get("/upload/filesystem")
        check(resp.status_code == 200, f"GET /upload/filesystem -> {resp.status_code}")
        token = extract_csrf(resp.data)
        resp = client.post(
            "/upload/filesystem",
            data={
                "csrf_token": token,
                "image": (io.BytesIO(fs_bytes), "smoke_fs.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        check(resp.status_code == 200, f"POST /upload/filesystem -> {resp.status_code}")
        check(
            b"uploaded successfully to the file system" in resp.data,
            "Filesystem upload did not report success",
        )

        # --- Database BLOB upload ------------------------------------------
        resp = client.get("/upload/blob")
        check(resp.status_code == 200, f"GET /upload/blob -> {resp.status_code}")
        token = extract_csrf(resp.data)
        resp = client.post(
            "/upload/blob",
            data={
                "csrf_token": token,
                "image": (io.BytesIO(blob_bytes), "smoke_blob.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        check(resp.status_code == 200, f"POST /upload/blob -> {resp.status_code}")
        check(
            b"uploaded successfully to the database" in resp.data,
            "BLOB upload did not report success",
        )

        # --- Dashboards render -----------------------------------------------
        for path in ("/gallery", "/statistics", "/comparison"):
            resp = client.get(path)
            check(resp.status_code == 200, f"GET {path} -> {resp.status_code}")

        # --- Both images retrievable, byte-for-byte -------------------------
        with app.app_context():
            fs_image = (
                Image.query.filter_by(storage_method="filesystem")
                .order_by(Image.id.desc())
                .first()
            )
            blob_image = (
                Image.query.filter_by(storage_method="blob")
                .order_by(Image.id.desc())
                .first()
            )
            check(fs_image is not None, "No filesystem image row found after upload")
            check(blob_image is not None, "No BLOB image row found after upload")
            fs_id, blob_id = fs_image.id, blob_image.id

        resp = client.get(f"/image/filesystem/{fs_id}")
        check(resp.status_code == 200, f"GET /image/filesystem/{fs_id} -> {resp.status_code}")
        check(resp.data == fs_bytes, "Filesystem image bytes did not round-trip correctly")

        resp = client.get(f"/image/blob/{blob_id}")
        check(resp.status_code == 200, f"GET /image/blob/{blob_id} -> {resp.status_code}")
        check(resp.data == blob_bytes, "BLOB image bytes did not round-trip correctly")

        # --- Validator rejects a fake image ----------------------------------
        resp = client.get("/upload/filesystem")
        token = extract_csrf(resp.data)
        resp = client.post(
            "/upload/filesystem",
            data={
                "csrf_token": token,
                "image": (io.BytesIO(b"not a real image"), "fake.png"),
            },
            content_type="multipart/form-data",
        )
        check(resp.status_code == 200, f"POST fake image -> {resp.status_code}")
        check(b"not a valid image" in resp.data, "Validator did not reject a fake image")

    print("SMOKE_TEST_OK: all checks passed (upload, retrieval, dashboards, validation).")


if __name__ == "__main__":
    try:
        run()
    except SmokeTestFailure as exc:
        print(f"SMOKE_TEST_FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - surfaced to the installer, not swallowed
        print(f"SMOKE_TEST_ERROR: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
