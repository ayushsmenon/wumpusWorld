"""
registry.py: the ingestion database (a single SQLite file).

Two tables:
  files - one row per ORIGINAL file: name, location, size, hash, status
  units - one row per extracted page/slide, linked to its file

The hash (sha256) of the file's bytes is how we recognise a file we already
processed, so we never do the same work twice.

This is the only file that talks to the database. If we later move to
Supabase, this is the only file that changes.
"""
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"   # <repo>/data
DB_PATH = DATA_DIR / "ingestion.db"
# page renders, slide pictures
EXTRACTED_DIR = DATA_DIR / "extracted"

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256        TEXT NOT NULL,
    name          TEXT,
    original_path TEXT,
    size_bytes    INTEGER,
    modified_at   TEXT,
    file_type     TEXT,
    status        TEXT NOT NULL,
    error         TEXT,
    unit_count    INTEGER DEFAULT 0,
    ingested_at   TEXT,
    UNIQUE (sha256, file_type)
);
CREATE TABLE IF NOT EXISTS units (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    unit_type   TEXT,
    number      INTEGER,
    text        TEXT,
    tables_json TEXT,
    images_json TEXT,
    has_visuals INTEGER,
    needs_ocr   INTEGER,
    UNIQUE (file_id, unit_type, number)
);
"""


def connect(db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def find_by_hash(conn, sha256, file_type):

    return conn.execute(
        "SELECT * FROM files WHERE sha256 = ? AND file_type = ?", (
            sha256, file_type)
    ).fetchone()


def save_result(conn, info, status, error, units):

    with conn:  # all-or-nothing: either everything is saved or nothing is
        conn.execute("DELETE FROM files WHERE sha256 = ? AND file_type = ?",
                     (info["sha256"], info["file_type"]))
        cur = conn.execute(
            """INSERT INTO files (sha256, name, original_path, size_bytes, modified_at,
                                  file_type, status, error, unit_count, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (info["sha256"], info["name"], info["original_path"], info["size_bytes"],
             info["modified_at"], info["file_type"], status, error, len(units),
             info["ingested_at"]),
        )
        file_id = cur.lastrowid
        conn.executemany(
            """INSERT INTO units (file_id, unit_type, number, text, tables_json,
                                  images_json, has_visuals, needs_ocr)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(file_id, u.unit_type, u.number, u.text,
              json.dumps(u.tables, ensure_ascii=False),
              json.dumps(u.images, ensure_ascii=False),
              int(u.has_visuals), int(u.needs_ocr)) for u in units],
        )
    return file_id


def get_units(conn, file_id):

    rows = conn.execute(
        "SELECT * FROM units WHERE file_id = ? ORDER BY number", (file_id,)
    ).fetchall()
    units = []
    for r in rows:
        units.append({
            "unit_type": r["unit_type"],
            "number": r["number"],
            "text": r["text"],
            "tables": json.loads(r["tables_json"]),
            "images": json.loads(r["images_json"]),
            "has_visuals": bool(r["has_visuals"]),
            "needs_ocr": bool(r["needs_ocr"]),
        })
    return units
