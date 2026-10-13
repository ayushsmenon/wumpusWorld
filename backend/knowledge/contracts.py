"""Typed contracts shared by ingestion, indexing, and retrieval."""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ContentRecord:
    """A normalized page, slide, or other source unit from ingestion."""

    source_id: str
    file_id: str
    course_id: str
    filename: str
    text: str
    source_type: str
    source_uri: str | None = None
    page_number: int | None = None
    slide_number: int | None = None
    section_title: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        required = {
            "source_id": self.source_id,
            "file_id": self.file_id,
            "course_id": self.course_id,
            "filename": self.filename,
            "source_type": self.source_type,
        }
        missing = [name for name, value in required.items() if not isinstance(value, str) or not value.strip()]
        if missing:
            raise ValueError(f"Missing required content metadata: {', '.join(missing)}")
        if not isinstance(self.text, str):
            raise ValueError("Content text must be a string")
        for name, value in (("page_number", self.page_number), ("slide_number", self.slide_number)):
            if value is not None and (not isinstance(value, int) or value < 1):
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class KnowledgeChunk:
    """A searchable chunk retaining its exact source location."""

    chunk_id: str
    source_id: str
    file_id: str
    course_id: str
    filename: str
    text: str
    chunk_index: int
    source_type: str
    source_uri: str | None = None
    page_number: int | None = None
    slide_number: int | None = None
    section_title: str | None = None
    content_hash: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    """Evidence returned to the tutor, including citation metadata."""

    chunk_id: str
    text: str
    score: float
    source_id: str
    file_id: str
    course_id: str
    filename: str
    source_uri: str | None = None
    page_number: int | None = None
    slide_number: int | None = None
    section_title: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
