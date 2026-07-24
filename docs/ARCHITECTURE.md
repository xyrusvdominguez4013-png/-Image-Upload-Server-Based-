# Architecture Documentation

## 1. System Architecture

```mermaid
graph TD
    Browser["Browser<br/>(Bootstrap 5 + Jinja2 + JS)"] -->|HTTP| Apache["Apache2<br/>+ mod_wsgi"]
    Apache -->|WSGI call| Flask["Flask App<br/>(Application Factory)"]
    Flask --> Routes["routes.py<br/>Blueprint: main"]
    Routes --> Forms["forms.py<br/>Flask-WTF / CSRF"]
    Routes --> Services["app/services/*"]
    Services --> FSStore["filesystem_storage.py"]
    Services --> BlobStore["blob_storage.py"]
    Services --> Validator["image_validator.py<br/>(Pillow)"]
    Services --> Stats["statistics_service.py"]
    Services --> Compare["comparison_service.py"]
    FSStore -->|write/read bytes| Disk[("uploads/ on disk")]
    Routes --> Models["models.py<br/>SQLAlchemy ORM"]
    Models --> MySQL[("MySQL 8<br/>images / image_blobs")]
    BlobStore --> Models
    FSStore --> Models
```

## 2. Entity Relationship Diagram

```mermaid
erDiagram
    IMAGES ||--o| IMAGE_BLOBS : "has (only if storage_method = blob)"
    IMAGES {
        bigint id PK
        varchar filename
        varchar original_filename
        varchar mime_type
        varchar extension
        bigint filesize
        enum storage_method
        varchar filepath "NULL for BLOB rows"
        datetime upload_time
        double upload_duration_ms
        double last_retrieval_duration_ms
    }
    IMAGE_BLOBS {
        bigint id PK
        bigint image_id FK
        longblob image_data
    }
```

## 3. Folder Structure

```
image-storage-demo/
├── run.py                     # Dev server entry point
├── config.py                  # Environment-based configuration
├── requirements.txt
├── install.sh                 # All-in-one installer: deps, DB, migrate, smoke test
├── scripts/
│   └── smoke_test.py          # End-to-end test invoked by install.sh
├── database/
│   ├── schema.sql             # Raw MySQL DDL
│   └── seed.sql                # Illustrative demo rows
├── deployment/
│   ├── apache/
│   │   ├── image-storage-demo.conf
│   │   └── image-storage-demo.wsgi
│   └── mysql/
├── app/
│   ├── __init__.py            # create_app() application factory
│   ├── models.py               # Image, ImageBlob SQLAlchemy models
│   ├── routes.py                # HTTP routes (Blueprint: main)
│   ├── forms.py                 # Flask-WTF upload form
│   ├── extensions.py            # db, migrate, csrf singletons
│   ├── services/
│   │   ├── filesystem_storage.py
│   │   ├── blob_storage.py
│   │   ├── image_validator.py
│   │   ├── statistics_service.py
│   │   └── comparison_service.py
│   ├── templates/
│   └── static/
└── docs/
```

## 4. Upload Workflow (File System)

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant Flask as Flask (routes.py)
    participant Validator as image_validator
    participant FS as filesystem_storage
    participant DB as MySQL

    User->>Browser: Choose image, click Upload
    Browser->>Flask: POST /upload/filesystem (multipart)
    Flask->>Validator: validate_upload(file)
    Validator-->>Flask: ok / error
    alt validation failed
        Flask-->>Browser: Re-render form with error (flash)
    else validation ok
        Flask->>FS: save_to_filesystem(file)
        FS->>FS: uuid4() filename, write to uploads/
        FS->>DB: INSERT INTO images (...)
        DB-->>FS: new Image row
        FS-->>Flask: Image
        Flask-->>Browser: Redirect to /gallery (success flash)
    end
```

## 5. Upload Workflow (Database BLOB)

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant Flask as Flask (routes.py)
    participant Validator as image_validator
    participant Blob as blob_storage
    participant DB as MySQL

    User->>Browser: Choose image, click Upload
    Browser->>Flask: POST /upload/blob (multipart)
    Flask->>Validator: validate_upload(file)
    Validator-->>Flask: ok / error
    alt validation failed
        Flask-->>Browser: Re-render form with error (flash)
    else validation ok
        Flask->>Blob: save_to_blob(file)
        Blob->>Blob: read raw bytes
        Blob->>DB: INSERT INTO images (...) + image_blobs (...)
        DB-->>Blob: new Image + ImageBlob rows
        Blob-->>Flask: Image
        Flask-->>Browser: Redirect to /gallery (success flash)
    end
```

## 6. Activity Diagram (Validation)

```mermaid
flowchart TD
    A([Start: file received]) --> B{Extension in<br/>allow-list?}
    B -- No --> R1[Reject: bad extension]
    B -- Yes --> C{Size within<br/>10 MB limit?}
    C -- No --> R2[Reject: too large]
    C -- Yes --> D{Browser MIME type<br/>in allow-list?}
    D -- No --> R3[Reject: bad MIME type]
    D -- Yes --> E[Decode with Pillow<br/>Image.verify]
    E --> F{Decodes as a<br/>real image?}
    F -- No --> R4[Reject: not a valid image]
    F -- Yes --> G{Decoded format<br/>matches allow-list?}
    G -- No --> R5[Reject: format mismatch]
    G -- Yes --> H([Accept: proceed to storage])
```

## 7. Flask Application Flow

1. `run.py` (dev) or `deployment/apache/image-storage-demo.wsgi` (prod) calls `create_app()`.
2. `create_app()` loads `Config` from environment variables, initializes
   `db`, `migrate`, and `csrf`, registers the `main` blueprint, and installs
   error handlers (413 / 404 / 500) and rotating-file logging.
3. Each request enters through `app/routes.py`, which delegates all
   business logic to `app/services/*` and never touches SQLAlchemy models
   or the filesystem directly for anything beyond simple lookups.
4. `app/models.py` defines the two tables described in the ERD above.
