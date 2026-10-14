import argparse
import hashlib
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from ingestion import registry, video_parser
from ingestion.image_parser import parse_image
from ingestion.models import (CORRUPT, PARSED, EmptyFileError, IngestionError,
                              UnsupportedFormatError)
from ingestion.office_parser import parse_office
from ingestion.pdf_parser import parse_pdf
from ingestion.slide_parser import parse_slides
from ingestion.video_parser import parse_video

PARSERS = {
    ".pdf": ("pdf", parse_pdf),
    ".pptx": ("pptx", parse_slides),
    ".docx": ("docx", parse_office), ".doc": ("doc", parse_office),
    ".odt": ("odt", parse_office), ".odp": ("odp", parse_office),
    ".ppt": ("ppt", parse_office),

    ".png": ("image", parse_image), ".jpg": ("image", parse_image),
    ".jpeg": ("image", parse_image), ".webp": ("image", parse_image),
    ".bmp": ("image", parse_image), ".gif": ("image", parse_image),
    ".tif": ("image", parse_image), ".tiff": ("image", parse_image),

    ".mp4": ("video", parse_video), ".mkv": ("video", parse_video),
    ".mov": ("video", parse_video), ".webm": ("video", parse_video),
    ".mp3": ("audio", parse_video), ".wav": ("audio", parse_video),
    ".m4a": ("audio", parse_video),
}
VISION_HELP = "pip install torch transformers pillow accelerate num2words"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_course_id(raw: str) -> str:
    course = re.sub(r"[^a-z0-9_-]+", "-", raw.strip().lower()).strip("-")
    if not course:
        raise ValueError("course_id is empty")
    return course


def make_file_id(course_id: str, sha: str) -> str:
    return hashlib.sha256(f"{course_id}:{sha}".encode()).hexdigest()[:16]


def run_vision(conn, file_id: str, force: bool = False) -> dict:
    from ingestion import vision
    try:
        return vision.caption_file(conn, file_id, force=force)
    except ImportError:
        return {"error": f"Vision skipped, libraries missing. Run: {VISION_HELP}"}
    except Exception as e:
        return {"error": f"Vision failed: {type(e).__name__}: {e}"}


def ingest_file(path, course_id: str, force: bool = False, vision: bool = True) -> dict:
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        return {"status": "missing", "message": f"No such file: {path}", "from_cache": False}

    course_id = clean_course_id(course_id)
    stat = path.stat()
    ext = path.suffix.lower()
    sha = sha256_of(path)
    file_id = make_file_id(course_id, sha)
    source_type = PARSERS[ext][0] if ext in PARSERS else (
        ext.lstrip(".") or "unknown")

    conn = registry.connect()
    existing = registry.find_by_file_id(conn, file_id)
    if existing and not force:
        result = {"status": existing["status"], "file_id": file_id, "course_id": course_id,
                  "source_type": source_type, "unit_count": existing["unit_count"],
                  "message": existing["error"] or "", "from_cache": True}
        if vision and existing["status"] == PARSED:
            result["vision"] = run_vision(conn, file_id)
        return result

    info = {
        "file_id": file_id,
        "course_id": course_id,
        "sha256": sha,
        "name": path.name,
        "original_path": str(path),
        "source_type": source_type,
        "file_ext": ext.lstrip("."),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }

    units, status, error = [], PARSED, None
    try:
        if stat.st_size == 0:
            raise EmptyFileError("File is empty (0 bytes)")
        if ext not in PARSERS:
            raise UnsupportedFormatError(f"Unsupported file type: '{ext}'")

        _, parser = PARSERS[ext]
        units = parser(path, registry.EXTRACTED_DIR / file_id)

        if not any(u.text or u.tables or u.images or u.needs_ocr for u in units):
            raise EmptyFileError("File has no readable content")
    except IngestionError as e:
        status, error, units = e.status, str(e), []
    except Exception as e:
        status, error, units = CORRUPT, f"{type(e).__name__}: {e}", []

    info["metadata"] = {
        "total_chars": sum(len(u.text or "") for u in units),
        "duration_sec": max((u.end_sec for u in units if u.end_sec is not None), default=None),
        "image_count": sum(len(u.images) for u in units),
    }
    registry.save_result(conn, info, status, error, units)
    result = {"status": status, "file_id": file_id, "course_id": course_id,
              "source_type": source_type, "unit_count": len(units),
              "message": error or "", "from_cache": False}
    if vision and status == PARSED:
        result["vision"] = run_vision(conn, file_id)
    return result


def delete_file(file_id: str, delete_original: bool = False) -> dict:

    if not re.fullmatch(r"[0-9a-f]{16}", file_id):
        raise ValueError("file_id must be 16 hex characters")
    conn = registry.connect()
    row = registry.delete_file_rows(conn, file_id)
    if row is None:
        return {"deleted": False, "file_id": file_id, "message": "No such file_id"}
    shutil.rmtree(registry.EXTRACTED_DIR / file_id, ignore_errors=True)
    if delete_original and row["original_path"]:
        Path(row["original_path"]).unlink(missing_ok=True)
    return {"deleted": True, "file_id": file_id, "filename": row["filename"],
            "course_id": row["course_id"], "original_deleted": delete_original}


def delete_course(course_id: str, delete_original: bool = False) -> int:
    conn = registry.connect()
    ids = [f["file_id"]
           for f in registry.list_files(conn, clean_course_id(course_id))]
    return sum(delete_file(i, delete_original)["deleted"] for i in ids)


def print_summary(path, result: dict):
    print(f"\n{Path(path).name}")
    print(f"  Status: {result['status']}" + ("   (already processed, reused saved result)"
                                             if result.get("from_cache") else ""))
    if result.get("message"):
        print(f"  Note: {result['message']}")
    if result.get("from_cache") and result["status"] != PARSED:
        print("  Tip: add --force to try this file again.")
    if result.get("file_id") and result["status"] == PARSED:
        conn = registry.connect()
        units = registry.get_units(conn, result["file_id"])
        print(f"  file_id: {result['file_id']}   course: {result['course_id']}   "
              f"type: {result['source_type']}")
        print(f"  Units: {len(units)}")
        if result["source_type"] == "video" or result["source_type"] == "audio":
            print(f"  Duration: {units[-1]['end_sec']:.0f}s   "
                  f"Language: {units[0]['metadata'].get('language')}")
            if result["source_type"] == "video":
                print(f"  Frames kept: {sum(len(u['images']) for u in units)}")
        else:
            print(
                f"  With tables: {[u['number'] for u in units if u['tables']]}")
            print(
                f"  With images/diagrams: {[u['number'] for u in units if u['has_visuals']]}")
            print(
                f"  Need OCR (scanned): {[u['number'] for u in units if u['needs_ocr']]}")
            missing = [u['number']
                       for u in units if u['metadata'].get('render_missing')]
            if missing:
                print(
                    f"  No slide image (install LibreOffice to get one): {missing}")
        described = sum(
            1 for u in units if u["caption"] or u["metadata"].get("text_from_vision"))
        print(f"  Units with a vision description: {described}")
        v = result.get("vision")
        if v:
            print(f"  Vision: {v['error']}" if "error" in v else
                  f"  Vision: {v['images']} images described, {v['failed']} failed, "
                  f"{v['no_image']} flagged units had no image to look at")


def collect_files(target: Path) -> list:
    if target.is_dir():
        return sorted(p for p in target.rglob("*")
                      if p.is_file() and p.suffix.lower() in PARSERS)
    return [target]


def main():
    ap = argparse.ArgumentParser(
        description="Ingest course files into the registry.")
    ap.add_argument(
        "path", help="a file, or a folder (ingests everything inside)")
    ap.add_argument("--course", required=True,
                    help="course id, e.g. my-course")
    ap.add_argument("--force", action="store_true",
                    help="re-process even if already ingested")
    ap.add_argument("--no-vision", action="store_true",
                    help="skip image descriptions")
    ap.add_argument("--no-frames", action="store_true",
                    help="don't sample frames from videos")
    args = ap.parse_args()

    if args.no_frames:
        video_parser.EXTRACT_FRAMES = False
    files = collect_files(Path(args.path).expanduser())
    if not files:
        print("No supported files found.")
        sys.exit(1)
    for f in files:
        print_summary(f, ingest_file(f, args.course,
                      force=args.force, vision=not args.no_vision))
    print(f"\nDatabase: {registry.DB_PATH}")


if __name__ == "__main__":
    main()
