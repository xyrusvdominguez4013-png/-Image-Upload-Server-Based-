# Image Storage Demo

**Direct File System Storage vs Database (BLOB) Storage — a Flask reference app**

A small, presentation-ready Flask application that uploads images two
different ways — straight to disk, and directly into a MySQL `LONGBLOB`
column — and lets you compare the two approaches side by side with real
numbers from your own uploads.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Layout](#project-layout)
- [Screenshots](#screenshots)
- [Quick Start (local dev, SQLite)](#quick-start-local-dev-sqlite)
- [Installation (Ubuntu Server, MySQL, Apache)](#installation-ubuntu-server-mysql-apache)
- [Database Configuration](#database-configuration)
- [Running the Application](#running-the-application)
- [Deployment with Apache + mod_wsgi](#deployment-with-apache--mod_wsgi)
- [Code Snippets](#code-snippets)
- [Security](#security)
- [Future Improvements](#future-improvements)

---

## Features

- **Two storage strategies, one codebase** — `filesystem` (UUID-named file
  on disk + metadata row) and `blob` (raw bytes in a MySQL `LONGBLOB`).
- **Upload validation** — extension allow-list, MIME allow-list, 10 MB size
  cap, and real image-content verification via Pillow (`Image.verify()`),
  so a renamed non-image file is rejected regardless of its extension.
- **Gallery** — responsive Bootstrap cards, filterable by storage method,
  searchable by filename, paginated, with a one-click **Delete** (with
  confirmation) that correctly removes both the metadata row and the
  underlying data — the on-disk file for filesystem images, or the
  `image_blobs` row for BLOB images.
- **Statistics dashboard** — live counts, upload-folder size, BLOB storage
  size, average upload/retrieval time, largest/smallest image, and a
  storage-distribution chart.
- **Comparison dashboard** — a static advantages/disadvantages/use-case
  matrix plus a *live* benchmark computed from this installation's own
  upload history.
- **Security** — CSRF protection (Flask-WTF), parameterized queries via
  SQLAlchemy, `secure_filename()` + UUID filenames, Jinja2 autoescaping,
  request size limits, and rotating file logging.

## Architecture

```
Browser → Apache2 + mod_wsgi → Flask (Application Factory)
                                   ├── routes.py (Blueprint)
                                   ├── forms.py (Flask-WTF / CSRF)
                                   ├── services/
                                   │     ├── image_validator.py (Pillow)
                                   │     ├── filesystem_storage.py → uploads/ (disk)
                                   │     ├── blob_storage.py       → MySQL image_blobs
                                   │     ├── statistics_service.py
                                   │     └── comparison_service.py
                                   └── models.py (SQLAlchemy) → MySQL 8
```

Full system architecture diagram, ER diagram, upload-workflow sequence
diagrams, and an activity diagram for the validation pipeline live in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (rendered as Mermaid — view on
GitHub or in any Mermaid-aware Markdown viewer).

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12+, Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-WTF |
| Database | MySQL 8 (PostgreSQL also supported via `DATABASE_URL`) |
| Frontend | HTML5, Bootstrap 5, Jinja2, vanilla JavaScript |
| Image processing | Pillow |
| Web server (prod) | Apache2 + mod_wsgi (Ubuntu Server 24.04 LTS, VirtualBox/VMware) |
| Version control | Git / GitHub |

## Project Layout

```
image-storage-demo/
├── run.py                     # Dev entry point
├── config.py                  # Env-based config
├── requirements.txt
├── install.sh                 # All-in-one installer (Ubuntu) -- see below
├── scripts/
│   └── smoke_test.py          # End-to-end test invoked by install.sh
├── .env.example
├── database/
│   ├── schema.sql
│   └── seed.sql
├── deployment/apache/
│   ├── image-storage-demo.conf
│   └── image-storage-demo.wsgi
├── app/
│   ├── __init__.py            # create_app()
│   ├── models.py               # Image, ImageBlob
│   ├── routes.py
│   ├── forms.py
│   ├── extensions.py
│   ├── services/
│   ├── templates/
│   └── static/
├── docs/                       # ARCHITECTURE.md, INSTALLATION.md
└── screenshots/
```

## Screenshots

Add screenshots of the running application here after your first demo run
(`screenshots/home.png`, `screenshots/gallery.png`,
`screenshots/statistics.png`, `screenshots/comparison.png`) — the
`screenshots/` folder is already tracked in the repo.

## Quick Start (local dev, SQLite)

For quick local iteration without standing up MySQL, the app falls back to
a SQLite database automatically:

```bash
python3 -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
export FLASK_APP=run.py         # set FLASK_APP=run.py on Windows
flask db init && flask db migrate -m "Initial schema" && flask db upgrade
flask run
```

Then open `http://127.0.0.1:5000`.

## Installation (Ubuntu Server, MySQL, Apache)

For the full production-style setup — a real Ubuntu Server 24.04 LTS VM,
MySQL 8, and Apache2 + mod_wsgi — see
**[docs/INSTALLATION.md](docs/INSTALLATION.md)**. The short version:

```bash
git clone https://github.com/xyrusvdominguez4013-png/image-storage-demo.git
cd image-storage-demo
chmod +x install.sh
sudo ./install.sh
```

`install.sh` is a single, idempotent, all-in-one installer. Every step
prints a colored PASS/FAIL line, with a summary at the end. Beyond system
packages, one run also:

1. Provisions the MySQL database and application user (random generated
   password).
2. Writes a working `.env` — `SECRET_KEY`, `DATABASE_URL`, and the
   `UPLOAD_FOLDER`/`LOG_FILE` paths, correctly pointed at wherever you
   actually cloned the repo.
3. Runs Flask-Migrate against the real database.
4. Runs an end-to-end smoke test — real image uploads through both
   storage methods, every dashboard, byte-for-byte retrieval, and
   validator rejection of a bad file — against a **disposable throwaway
   database** that's dropped afterward, so your real data is never
   touched.
5. Hands file ownership back to the invoking user so `flask run` works
   immediately afterward.

It also proactively repairs a couple of common real-world failure modes
on fresh Ubuntu VMs: an interrupted dpkg state, and the apt/dpkg lock
being held by `unattended-upgrades` right after boot (it waits instead
of failing). Flags: `--skip-smoke-test`, `--skip-db` (see
[docs/INSTALLATION.md](docs/INSTALLATION.md) for details).

## Database Configuration

`install.sh` provisions the database automatically (see above). See
[database/schema.sql](database/schema.sql) for the raw DDL, and
[docs/INSTALLATION.md](docs/INSTALLATION.md#4-manual-database-setup-only-if-you-used---skip-db)
for the manual `CREATE DATABASE` / `CREATE USER` steps if you used
`--skip-db`. `DATABASE_URL` in `.env` controls which database the app
connects to (MySQL by default in production, SQLite by default in local
dev):

```
DATABASE_URL=mysql+pymysql://image_demo_user:CHANGE_ME@localhost:3306/image_storage_demo
```

## Running the Application

```bash
source venv/bin/activate
flask run                        # dev server, http://127.0.0.1:5000
```

Production runs under Apache + mod_wsgi (see below) rather than the dev
server.

## Deployment with Apache + mod_wsgi

```bash
sudo cp deployment/apache/image-storage-demo.conf /etc/apache2/sites-available/
sudo a2ensite image-storage-demo
sudo a2enmod wsgi
sudo systemctl reload apache2
```

Full walkthrough, including path/VirtualHost adjustments and a Gunicorn +
Nginx alternative, in [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Code Snippets

A few of the patterns this project is meant to demonstrate (see the
linked files for full context):

**Secure filename + UUID generation** — [app/services/filesystem_storage.py](app/services/filesystem_storage.py)
```python
original_filename = secure_filename(file_storage.filename)
unique_filename = f"{uuid.uuid4().hex}.{extension}"
file_storage.save(os.path.join(upload_folder, unique_filename))
```

**Binary storage with `LargeBinary`** — [app/models.py](app/models.py)
```python
class ImageBlob(db.Model):
    image_data = db.Column(db.LargeBinary(length=(2**32) - 1), nullable=False)  # LONGBLOB
```

**Streaming a BLOB image back out with `send_file()`** — [app/routes.py](app/routes.py)
```python
@main_bp.route("/image/blob/<int:image_id>")
def stream_blob_image(image_id):
    image = Image.query.get_or_404(image_id)
    data, duration_ms = read_from_blob(image)
    return send_file(io.BytesIO(data), mimetype=image.mime_type)
```

**Image-content verification with Pillow** — [app/services/image_validator.py](app/services/image_validator.py)
```python
with PILImage.open(file_storage.stream) as img:
    img.verify()          # raises if this isn't a decodable image
```

## Security

- CSRF protection on every form (Flask-WTF `CSRFProtect`)
- SQL injection prevention via SQLAlchemy's parameterized queries (no raw
  string-interpolated SQL anywhere in the app)
- `secure_filename()` + UUID filenames — the original filename is never
  used to construct a filesystem path
- Jinja2 autoescaping (on by default, not disabled anywhere) for XSS
  prevention
- `MAX_CONTENT_LENGTH` (10 MB) enforced by Flask, plus a matching
  `LimitRequestBody` in the Apache vhost
- MIME allow-list **and** Pillow content verification (belt-and-suspenders
  against spoofed `Content-Type`/extension)
- Rotating file logging (`RotatingFileHandler`) for both info-level
  operational events and exception tracebacks

## Future Improvements

- Object-storage backend (S3-compatible) as a third storage strategy
- Thumbnail generation/caching for the gallery instead of full-size
  streaming
- Per-user accounts and ownership of uploaded images
- Async/background processing for large-batch uploads
