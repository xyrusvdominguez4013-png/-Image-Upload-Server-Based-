"""Static comparison matrix plus a small live benchmark, used by the
Comparison dashboard to back up its qualitative claims with real numbers
from this installation's own upload history.
"""
from dataclasses import dataclass

from app.services.statistics_service import Statistics


COMPARISON_MATRIX = [
    {
        "category": "Upload speed",
        "filesystem": "Fast — a single streamed write() to disk.",
        "blob": "Slower — bytes are buffered and sent through the DB "
                "connection, plus transaction/log overhead.",
    },
    {
        "category": "Retrieval speed",
        "filesystem": "Fast for small/medium files; OS page cache helps a lot; "
                       "can be served directly by the web server or a CDN.",
        "blob": "Slower for large files; every read goes through the DB "
                "engine and the app process.",
    },
    {
        "category": "Database size",
        "filesystem": "Stays small — only metadata rows.",
        "blob": "Grows directly with total image bytes uploaded.",
    },
    {
        "category": "Disk usage",
        "filesystem": "Images accumulate in the uploads/ directory, "
                       "separate from the database files.",
        "blob": "Images live inside MySQL's data directory alongside "
                "every other table.",
    },
    {
        "category": "Backup complexity",
        "filesystem": "Two things to back up in sync: the database AND "
                       "the uploads/ directory.",
        "blob": "One thing to back up: a single database dump/snapshot "
                "contains everything.",
    },
    {
        "category": "Scalability",
        "filesystem": "Scales well horizontally with object storage "
                       "(S3/NFS) behind multiple app servers.",
        "blob": "Database becomes the bottleneck; harder to shard/scale "
                "as BLOB volume grows.",
    },
    {
        "category": "Security",
        "filesystem": "Requires careful path/permission handling to avoid "
                       "directory traversal or executing uploaded files.",
        "blob": "Inherits the database's access control and encryption-at-rest; "
                "no separately exposed file path to guard.",
    },
    {
        "category": "Ease of maintenance",
        "filesystem": "Simple to reason about; orphaned files/rows can "
                       "drift out of sync if not handled carefully.",
        "blob": "Metadata and bytes are always transactionally consistent "
                "with each other.",
    },
    {
        "category": "Best use cases",
        "filesystem": "Large volumes of user media (photos, videos, "
                       "documents) served publicly, e.g. via CDN.",
        "blob": "Small numbers of tightly-coupled images that must be "
                "transactionally consistent with their owning record, "
                "e.g. ID document scans, signatures.",
    },
]


@dataclass
class Benchmark:
    avg_upload_ms_filesystem: float | None
    avg_upload_ms_blob: float | None
    faster_upload_method: str | None


def build_benchmark(stats: Statistics) -> Benchmark:
    fs = stats.avg_upload_duration_by_method.get("filesystem")
    blob = stats.avg_upload_duration_by_method.get("blob")

    faster = None
    if fs is not None and blob is not None:
        faster = "filesystem" if fs < blob else "blob"

    return Benchmark(
        avg_upload_ms_filesystem=fs,
        avg_upload_ms_blob=blob,
        faster_upload_method=faster,
    )
