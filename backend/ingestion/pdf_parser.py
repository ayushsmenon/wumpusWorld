import statistics
from collections import Counter
from pathlib import Path

import pymupdf

try:
    from backend.ingestion.models import (CorruptFileError, EmptyFileError, ParsedUnit,
                                          PasswordProtectedError)
except ImportError:
    from ingestion.models import (CorruptFileError, EmptyFileError, ParsedUnit,
                                  PasswordProtectedError)

MIN_TEXT_CHARS = 25
BIG_IMAGE_FRACTION = 0.05
DIAGRAM_EXTRA_DRAWINGS = 10
SCAN_IMAGE_FRACTION = 0.5
MIN_FILLED_FRACTION = 0.5
RENDER_DPI = 150


def find_repeated_images(doc) -> set:
    counts = Counter()
    for page in doc:
        for xref in {img[0] for img in page.get_images(full=True)}:
            counts[xref] += 1
    limit = max(3, len(doc) * 0.3)
    return {xref for xref, n in counts.items() if n >= limit}


def extract_tables(page):
    tables, rejected = [], 0
    try:
        for table in page.find_tables().tables:
            rows = [[(cell or "").replace("\n", " ").strip() for cell in row]
                    for row in table.extract()]
            if len(rows) < 2 or len(rows[0]) < 2:
                continue
            cells = [c for row in rows for c in row]
            if sum(1 for c in cells if c) / len(cells) >= MIN_FILLED_FRACTION:
                tables.append(rows)
            else:
                rejected += 1
    except Exception:
        pass
    return tables, rejected


def find_images(page, repeated) -> list:
    page_area = page.rect.width * page.rect.height
    found = []
    for img in page.get_images(full=True):
        xref = img[0]
        if xref in repeated:
            continue
        for rect in page.get_image_rects(xref):
            if rect.width * rect.height > BIG_IMAGE_FRACTION * page_area:
                found.append({
                    "kind": "picture",
                    "path": None,
                    "bbox": [round(v) for v in rect],
                    "width": round(rect.width),
                    "height": round(rect.height),
                })
    return found


def render_page(page, number, out_dir: Path, prefix: str = "page") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{number:04d}.png"
    pix = page.get_pixmap(dpi=RENDER_DPI)
    pix.save(str(out_dir / filename))
    return {"kind": "page_render", "path": f"{out_dir.name}/{filename}",
            "bbox": None, "width": pix.width, "height": pix.height}


def parse_pdf(path: Path, out_dir: Path) -> list:
    try:
        doc = pymupdf.open(path)
    except Exception as e:
        raise CorruptFileError(f"Could not open PDF: {e}") from e

    try:
        if doc.needs_pass:
            raise PasswordProtectedError("PDF is password protected")
        if doc.page_count == 0:
            raise EmptyFileError("PDF has no pages")

        repeated = find_repeated_images(doc)
        drawing_counts = [len(p.get_drawings()) for p in doc]
        baseline = statistics.median(drawing_counts)

        units = []
        for index, page in enumerate(doc):
            number = index + 1
            text = page.get_text().strip()
            tables, sparse_grids = extract_tables(page)
            images = find_images(page, repeated)
            has_diagram = (sparse_grids > 0
                           or drawing_counts[index] > baseline + DIAGRAM_EXTRA_DRAWINGS)
            has_visuals = bool(images) or has_diagram
            page_area = (page.rect.width * page.rect.height) or 1
            biggest = max((i["width"] * i["height"]
                          for i in images), default=0) / page_area
            needs_ocr = len(
                text) < MIN_TEXT_CHARS and biggest > SCAN_IMAGE_FRACTION
            if has_visuals:
                images.append(render_page(page, number, out_dir))
            units.append(ParsedUnit(
                "page", number, text, tables, images, has_visuals, needs_ocr,
                metadata={"sparse_grids": sparse_grids,
                          "drawing_count": drawing_counts[index]},
            ))
        return units
    finally:
        doc.close()
