import re
from dataclasses import asdict, dataclass
from typing import Any, Sequence


def format_timestamp(seconds: float | int | None) -> str:
    if seconds is None or seconds < 0:
        return ""
    total_seconds = int(round(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes:02d}:{remaining_seconds:02d}"


def format_source_location(
    source_type: str | None = None,
    page_number: int | None = None,
    slide_number: int | None = None,
    video_timestamp: float | int | None = None,
) -> str:
    if page_number is not None:
        return f"Page {page_number}"
    if slide_number is not None:
        return f"Slide {slide_number}"
    if video_timestamp is not None:
        formatted_time = format_timestamp(video_timestamp)
        return f"Timestamp {formatted_time}" if formatted_time else "Video"
    if source_type:
        normalized = source_type.strip().lower()
        if normalized in {"pdf", "document"}:
            return "Document"
        if normalized in {"pptx", "slides", "slide"}:
            return "Slide"
        if normalized in {"video", "audio"}:
            return "Video"
    return "Source"


def format_citation_label(
    filename: str | None = None,
    source_type: str | None = None,
    page_number: int | None = None,
    slide_number: int | None = None,
    video_timestamp: float | int | None = None,
    topic_title: str | None = None,
) -> str:
    location = format_source_location(
        source_type=source_type,
        page_number=page_number,
        slide_number=slide_number,
        video_timestamp=video_timestamp,
    )
    parts = []
    if filename and filename.strip():
        parts.append(filename.strip())
    if location and location != "Source":
        parts.append(location)
    elif not parts:
        parts.append("Source")
    label = " - ".join(parts) if len(parts) > 1 else parts[0]
    if topic_title and topic_title.strip():
        label = f"{label} [{topic_title.strip()}]"
    return label


def format_citation_marker(citation_id: int | str) -> str:
    return f"[{citation_id}]"


@dataclass(frozen=True)
class Citation:
    id: int
    source_type: str
    source_uri: str | None = None
    filename: str | None = None
    page_number: int | None = None
    slide_number: int | None = None
    video_timestamp: float | None = None
    topic_title: str | None = None
    location: str = ""
    label: str = ""
    text_snippet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_citation(
    citation_id: int,
    source_type: str = "document",
    source_uri: str | None = None,
    filename: str | None = None,
    page_number: int | None = None,
    slide_number: int | None = None,
    video_timestamp: float | None = None,
    topic_title: str | None = None,
    text_snippet: str | None = None,
) -> Citation:
    location = format_source_location(
        source_type=source_type,
        page_number=page_number,
        slide_number=slide_number,
        video_timestamp=video_timestamp,
    )
    label = format_citation_label(
        filename=filename,
        source_type=source_type,
        page_number=page_number,
        slide_number=slide_number,
        video_timestamp=video_timestamp,
        topic_title=topic_title,
    )
    snippet = text_snippet.strip()[:200] if isinstance(text_snippet, str) else None
    return Citation(
        id=citation_id,
        source_type=source_type or "document",
        source_uri=source_uri,
        filename=filename,
        page_number=page_number,
        slide_number=slide_number,
        video_timestamp=video_timestamp,
        topic_title=topic_title,
        location=location,
        label=label,
        text_snippet=snippet,
    )


def build_context_and_citations(
    chunks: Sequence[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    context_blocks: list[str] = []
    citations: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        citation = create_citation(
            citation_id=idx,
            source_type=chunk.get("source_type") or "document",
            source_uri=chunk.get("source_uri"),
            filename=chunk.get("filename"),
            page_number=chunk.get("page_number"),
            slide_number=chunk.get("slide_number"),
            video_timestamp=chunk.get("video_timestamp"),
            topic_title=chunk.get("topic_title"),
            text_snippet=chunk.get("chunk_text") or chunk.get("text"),
        )
        citations.append(citation.to_dict())
        marker = format_citation_marker(idx)
        text = (chunk.get("chunk_text") or chunk.get("text") or "").strip()
        context_blocks.append(f"{marker} {text}")
    context_text = "\n\n".join(context_blocks)
    return context_text, citations


def extract_cited_ids(response_text: str) -> list[int]:
    if not response_text:
        return []
    matches = re.findall(r"\[(\d+)\]", response_text)
    seen = set()
    ordered_ids = []
    for match in matches:
        citation_id = int(match)
        if citation_id not in seen:
            seen.add(citation_id)
            ordered_ids.append(citation_id)
    return ordered_ids
