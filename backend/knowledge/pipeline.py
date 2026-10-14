import hashlib
import os
from pathlib import Path
from typing import Any, Sequence

from backend.ingestion.image_parser import parse_image
from backend.ingestion.office_parser import parse_office
from backend.ingestion.pdf_parser import parse_pdf
from backend.ingestion.slide_parser import parse_slides
from backend.ingestion.video_parser import parse_video
from backend.knowledge.chunking import TextChunker
from backend.knowledge.contracts import ContentRecord
from backend.knowledge.embeddings import LocalSentenceTransformerProvider
from backend.knowledge.storage import PostgresKnowledgeStore


PARSERS = {
    ".pdf": ("pdf", parse_pdf),
    ".pptx": ("pptx", parse_slides),
    ".docx": ("docx", parse_office),
    ".doc": ("doc", parse_office),
    ".odt": ("odt", parse_office),
    ".odp": ("odp", parse_office),
    ".ppt": ("ppt", parse_office),
    ".png": ("image", parse_image),
    ".jpg": ("image", parse_image),
    ".jpeg": ("image", parse_image),
    ".webp": ("image", parse_image),
    ".bmp": ("image", parse_image),
    ".mp4": ("video", parse_video),
    ".mkv": ("video", parse_video),
    ".mov": ("video", parse_video),
    ".webm": ("video", parse_video),
    ".mp3": ("audio", parse_video),
    ".wav": ("audio", parse_video),
    ".m4a": ("audio", parse_video),
}


class KnowledgePipeline:
    def __init__(
        self,
        store: PostgresKnowledgeStore | None = None,
        embedder: LocalSentenceTransformerProvider | None = None,
        chunker: TextChunker | None = None,
    ) -> None:
        self.store = store or PostgresKnowledgeStore.from_environment()
        self.embedder = embedder or LocalSentenceTransformerProvider(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            cache_folder=os.getenv("EMBEDDING_CACHE_DIR") or os.getenv("HF_HOME", "D:/wumpus_cache"),
            local_files_only=True,
            device="cpu",
        )
        self.chunker = chunker or TextChunker(chunk_size=1200, overlap=150)

    def compute_file_id(self, course_id: str, file_bytes: bytes) -> str:
        sha = hashlib.sha256(file_bytes).hexdigest()
        return hashlib.sha256(f"{course_id}:{sha}".encode()).hexdigest()[:16]

    def ingest_and_index(
        self,
        file_path: str | Path,
        course_id: str,
        topic_id: int | None = None,
        source_uri: str | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext not in PARSERS:
            raise ValueError(f"Unsupported file format: {ext}")

        source_type, parser_fn = PARSERS[ext]
        with open(path, "rb") as fp:
            file_bytes = fp.read()

        file_id = self.compute_file_id(course_id, file_bytes)
        out_dir = Path("data/extracted") / file_id
        out_dir.mkdir(parents=True, exist_ok=True)

        parsed_units = parser_fn(path, out_dir)
        records: list[ContentRecord] = []

        for unit in parsed_units:
            text = unit.text or ""
            if unit.notes:
                text = f"{text}\n\nNotes: {unit.notes}".strip()
            if not text.strip() and unit.has_visuals:
                text = f"Visual content: {unit.unit_type} {unit.number}"

            if not text.strip():
                continue

            record = ContentRecord(
                source_id=f"{file_id}:{unit.unit_type[:1]}{unit.number}",
                file_id=file_id,
                course_id=str(course_id),
                filename=path.name,
                text=text,
                source_type=source_type,
                source_uri=source_uri or str(path.name),
                page_number=unit.number if unit.unit_type == "page" else None,
                slide_number=unit.number if unit.unit_type == "slide" else None,
                video_timestamp=unit.start_sec if unit.start_sec is not None else None,
                topic_id=topic_id,
                section_title=unit.metadata.get("title") if unit.metadata else None,
                metadata={
                    "has_visuals": unit.has_visuals,
                    "tables_count": len(unit.tables),
                    "images_count": len(unit.images),
                    "start_sec": unit.start_sec,
                    "end_sec": unit.end_sec,
                },
            )
            records.append(record)

        if not records:
            return {
                "file_id": file_id,
                "course_id": course_id,
                "units_count": 0,
                "chunks_count": 0,
                "status": "empty",
            }

        chunks = self.chunker.chunk_many(records)
        chunk_texts = [c.text for c in chunks]
        embedded_vectors = self.embedder.embed(chunk_texts)
        embeddings_map = {c.chunk_id: vec for c, vec in zip(chunks, embedded_vectors)}

        self.store.index_document(chunks=chunks, embeddings=embeddings_map)

        return {
            "file_id": file_id,
            "course_id": course_id,
            "filename": path.name,
            "source_type": source_type,
            "units_count": len(records),
            "chunks_count": len(chunks),
            "status": "indexed",
        }
