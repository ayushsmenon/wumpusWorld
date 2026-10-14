"""
tables:
  files - one row per ORIGINAL file (file_id, course_id, filename, source_type, ...)
  units - one row per page/slide/segment (source_id, text, tables, images, ...)
"""
import json
import sqlite3
from pathlib import Path

from ingestion.models import make_source_id

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "ingestion.db"
EXTRACTED_DIR = DATA_DIR / "extracted"

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    file_id       TEXT PRIMARY KEY,
    course_id     TEXT NOT NULL,
    filename      TEXT NOT NULL,
    original_path TEXT,
    source_type   TEXT NOT NULL,
    file_ext      TEXT,
    sha256        TEXT NOT NULL,
    size_bytes    INTEGER,
    modified_at   TEXT,
    status        TEXT NOT NULL,
    error         TEXT,
    unit_count    INTEGER DEFAULT 0,
    metadata_json TEXT,
    ingested_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_course ON files(course_id);

CREATE TABLE IF NOT EXISTS units (
    source_id     TEXT PRIMARY KEY,
    file_id       TEXT NOT NULL REFERENCES files(file_id) ON DELETE CASCADE,
    course_id     TEXT NOT NULL,
    filename      TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    unit_type     TEXT NOT NULL,
    number        INTEGER NOT NULL,
    start_sec     REAL,
    end_sec       REAL,
    text          TEXT,
    notes         TEXT,
    caption       TEXT,
    char_count    INTEGER,
    tables_json   TEXT,
    images_json   TEXT,
    has_visuals   INTEGER,
    needs_ocr     INTEGER,
    metadata_json TEXT,
    UNIQUE (file_id, unit_type, number)
);
CREATE INDEX IF NOT EXISTS idx_units_file ON units(file_id);
CREATE INDEX IF NOT EXISTS idx_units_course ON units(course_id);
"""


def connect(db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        conn.executescript(
            "DROP TABLE IF EXISTS units; DROP TABLE IF EXISTS files;")
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    else:
        conn.executescript(SCHEMA)
    return conn


def find_by_file_id(conn, file_id):
    return conn.execute("SELECT * FROM files WHERE file_id = ?", (file_id,)).fetchone()


def save_result(conn, info, status, error, units):
    file_id = info["file_id"]
    with conn:
        conn.execute("DELETE FROM files WHERE file_id = ?",
                     (file_id,))
        conn.execute(
            """INSERT INTO files (file_id, course_id, filename, original_path, source_type,
                                  file_ext, sha256, size_bytes, modified_at, status, error,
                                  unit_count, metadata_json, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, info["course_id"], info["name"], info["original_path"],
             info["source_type"], info["file_ext"], info["sha256"], info["size_bytes"],
             info["modified_at"], status, error, len(units),
             json.dumps(info.get("metadata", {}), ensure_ascii=False), info["ingested_at"]),
        )
        conn.executemany(
            """INSERT INTO units (source_id, file_id, course_id, filename, source_type,
                                  unit_type, number, start_sec, end_sec, text, notes,
                                  char_count, tables_json, images_json, has_visuals,
                                  needs_ocr, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(make_source_id(file_id, u.unit_type, u.number), file_id, info["course_id"],
              info["name"], info["source_type"], u.unit_type, u.number,
              u.start_sec, u.end_sec, u.text, u.notes, len(u.text or ""),
              json.dumps(u.tables, ensure_ascii=False),
              json.dumps(u.images, ensure_ascii=False),
              int(u.has_visuals), int(u.needs_ocr),
              json.dumps(u.metadata, ensure_ascii=False)) for u in units],
        )
    return file_id


def _full_text(text, caption):
    parts = [text or ""]
    if caption:
        parts.append("[Figure description] " + caption)
    return "\n\n".join(p for p in parts if p)


def _unit_row_to_dict(r):
    return {
        "full_text": _full_text(r["text"], r["caption"]),
        "source_id": r["source_id"],
        "file_id": r["file_id"],
        "course_id": r["course_id"],
        "filename": r["filename"],
        "source_type": r["source_type"],
        "unit_type": r["unit_type"],
        "number": r["number"],
        "start_sec": r["start_sec"],
        "end_sec": r["end_sec"],
        "text": r["text"],
        "notes": r["notes"],
        "caption": r["caption"],
        "char_count": r["char_count"],
        "tables": json.loads(r["tables_json"] or "[]"),
        "images": json.loads(r["images_json"] or "[]"),
        "has_visuals": bool(r["has_visuals"]),
        "needs_ocr": bool(r["needs_ocr"]),
        "metadata": json.loads(r["metadata_json"] or "{}"),
    }


def get_units(conn, file_id):
    rows = conn.execute(
        "SELECT * FROM units WHERE file_id = ? ORDER BY number", (file_id,)).fetchall()
    return [_unit_row_to_dict(r) for r in rows]


def get_course_units(conn, course_id):
    rows = conn.execute(
        "SELECT * FROM units WHERE course_id = ? ORDER BY file_id, number", (
            course_id,)
    ).fetchall()
    return [_unit_row_to_dict(r) for r in rows]


def list_files(conn, course_id=None):
    if course_id:
        return conn.execute("SELECT * FROM files WHERE course_id = ? ORDER BY filename",
                            (course_id,)).fetchall()
    return conn.execute("SELECT * FROM files ORDER BY course_id, filename").fetchall()


def set_caption(conn, source_id, caption):
    with conn:
        conn.execute(
            "UPDATE units SET caption = ? WHERE source_id = ?", (caption, source_id))


def set_vision_result(conn, source_id, caption, images, text=None, metadata=None):
    """
      caption  - combined description of the unit's images
      images   - the unit's images list, each now carrying its own "caption"
      text     - only for scanned units (needs_ocr): the transcribed text
      metadata - extra keys merged into the unit's metadata
    """
    with conn:
        row = conn.execute("SELECT metadata_json FROM units WHERE source_id = ?",
                           (source_id,)).fetchone()
        if row is None:
            return
        meta = json.loads(row["metadata_json"] or "{}")
        meta.update(metadata or {})
        if text is None:
            conn.execute(
                "UPDATE units SET caption = ?, images_json = ?, metadata_json = ? WHERE source_id = ?",
                (caption, json.dumps(images, ensure_ascii=False),
                 json.dumps(meta, ensure_ascii=False), source_id))
        else:
            conn.execute(
                """UPDATE units SET caption = ?, images_json = ?, text = ?, char_count = ?,
                   metadata_json = ? WHERE source_id = ?""",
                (caption, json.dumps(images, ensure_ascii=False), text, len(text),
                 json.dumps(meta, ensure_ascii=False), source_id))


def delete_file_rows(conn, file_id):
    row = conn.execute("SELECT file_id, filename, original_path, course_id FROM files "
                       "WHERE file_id = ?", (file_id,)).fetchone()
    if row is None:
        return None
    with conn:
        conn.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
    return dict(row)
