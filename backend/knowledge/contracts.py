from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ContentRecord:
    source_id: str
    file_id: str
    course_id: str
    filename: str
    text: str
    source_type: str
    source_uri: str | None = None
    page_number: int | None = None
    slide_number: int | None = None
    video_timestamp: float | None = None
    topic_id: int | None = None
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
        if self.video_timestamp is not None and (not isinstance(self.video_timestamp, (int, float)) or self.video_timestamp < 0):
            raise ValueError("video_timestamp must be a non-negative number")


@dataclass(frozen=True)
class KnowledgeChunk:
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
    video_timestamp: float | None = None
    topic_id: int | None = None
    section_title: str | None = None
    content_hash: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
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
    video_timestamp: float | None = None
    topic_id: int | None = None
    section_title: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
