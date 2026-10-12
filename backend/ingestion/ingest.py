
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from ingestion import registry
from ingestion.models import (PARSED, EmptyFileError, IngestionError,
                              UnsupportedFormatError, CORRUPT)
from ingestion.pdf_parser import parse_pdf
from ingestion.slide_parser import parse_slides

PARSERS = {
    ".pdf": ("pdf", parse_pdf),
    ".pptx": ("slides", parse_slides),
}
NOT_YET = {
    ".ppt": "Old .ppt format is not supported. Save it as .pptx or export to PDF.",
    ".mp4": "Video support is not built yet.",
    ".mkv": "Video support is not built yet.",
    ".mov": "Video support is not built yet.",
    ".mp3": "Audio support is not built yet.",
}


def sha256_of(path: Path) -> str:

    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ingest_file(path, force: bool = False) -> dict:

    path = Path(path).expanduser().resolve()
    if not path.is_file():
        return {"status": "missing", "message": f"No such file: {path}", "from_cache": False}

    stat = path.stat()
    ext = path.suffix.lower()
    file_type = ext.lstrip(".")
    sha = sha256_of(path)

    conn = registry.connect()
    existing = registry.find_by_hash(conn, sha, file_type)
    if existing and not force:
        return {"status": existing["status"], "file_id": existing["id"],
                "unit_count": existing["unit_count"], "message": existing["error"] or "",
                "from_cache": True}

    info = {
        "sha256": sha,
        "name": path.name,
        "original_path": str(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "file_type": file_type,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }

    units, status, error = [], PARSED, None
    try:
        if stat.st_size == 0:
            raise EmptyFileError("File is empty (0 bytes)")
        if ext in NOT_YET:
            raise UnsupportedFormatError(NOT_YET[ext])
        if ext not in PARSERS:
            raise UnsupportedFormatError(f"Unsupported file type: '{ext}'")

        _, parser = PARSERS[ext]
        units = parser(path, registry.EXTRACTED_DIR / sha[:12])

        if not any(u.text or u.tables or u.images or u.needs_ocr for u in units):
            raise EmptyFileError("File has no readable content")
    except IngestionError as e:
        status, error, units = e.status, str(e), []
    except Exception as e:
        status, error, units = CORRUPT, f"{type(e).__name__}: {e}", []

    file_id = registry.save_result(conn, info, status, error, units)
    return {"status": status, "file_id": file_id, "unit_count": len(units),
            "message": error or "", "from_cache": False}


def print_summary(result: dict):
    print(f"Status: {result['status']}" + ("   (already processed, reused saved result)"
                                           if result.get("from_cache") else ""))
    if result.get("message"):
        print(f"Note: {result['message']}")
    if result.get("from_cache") and result["status"] != PARSED:
        print("Tip: add --force to try this file again.")
    if result.get("file_id") and result["status"] == PARSED:
        conn = registry.connect()
        units = registry.get_units(conn, result["file_id"])
        print(f"Units (pages/slides): {len(units)}")
        print(f"With tables: {[u['number'] for u in units if u['tables']]}")
        print(
            f"With images/diagrams: {[u['number'] for u in units if u['has_visuals']]}")
        print(
            f"Need OCR (scanned): {[u['number'] for u in units if u['needs_ocr']]}")
        print(f"Database: {registry.DB_PATH}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m ingestion.ingest yourfile.pdf [--force]")
        sys.exit(1)
    print_summary(ingest_file(sys.argv[1], force="--force" in sys.argv))
