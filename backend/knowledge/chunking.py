"""Deterministic, source-preserving text chunking."""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from typing import Iterable

from .contracts import ContentRecord, KnowledgeChunk


class ChunkingError(ValueError):
    """Raised when chunking configuration or input is invalid."""


class TextChunker:
    def __init__(self, chunk_size: int = 1200, overlap: int = 150, min_chunk_size: int = 80) -> None:
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ChunkingError("chunk_size must be positive and overlap must be smaller than chunk_size")
        if min_chunk_size < 0 or min_chunk_size > chunk_size:
            raise ChunkingError("min_chunk_size must be between zero and chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size

    def chunk(self, record: ContentRecord) -> list[KnowledgeChunk]:
        record.validate()
        text = _normalize_text(record.text)
        if not text:
            return []

        pieces: list[str] = []
        for section in _split_sections(text):
            pieces.extend(_split_section(section, self.chunk_size, self.overlap))

        chunks: list[KnowledgeChunk] = []
        for index, piece in enumerate(pieces):
            if len(piece) < self.min_chunk_size and chunks:
                previous = chunks[-1]
                merged = f"{previous.text}\n\n{piece}"
                if len(merged) <= self.chunk_size + self.overlap:
                    chunks[-1] = replace(previous, text=merged, content_hash=_hash_text(merged))
                    continue
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{record.file_id}:{record.source_id}:{index}",
                    source_id=record.source_id,
                    file_id=record.file_id,
                    course_id=record.course_id,
                    filename=record.filename,
                    text=piece,
                    chunk_index=index,
                    source_type=record.source_type,
                    source_uri=record.source_uri,
                    page_number=record.page_number,
                    slide_number=record.slide_number,
                    section_title=record.section_title,
                    content_hash=_hash_text(piece),
                    metadata=dict(record.metadata),
                )
            )
        return chunks

    def chunk_many(self, records: Iterable[ContentRecord]) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for record in records:
            chunks.extend(self.chunk(record))
        return chunks


def _normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", text)).strip()


def _split_sections(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]


def _split_section(section: str, chunk_size: int, overlap: int) -> list[str]:
    if len(section) <= chunk_size:
        return [section]
    sentences = re.split(r"(?<=[.!?])\s+", section)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if len(sentence) > chunk_size:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_long_text(sentence, chunk_size, overlap))
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > chunk_size:
            pieces.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {sentence}".strip()
            if len(current) > chunk_size:
                current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    pieces: list[str] = []
    current_words: list[str] = []
    for word in words:
        if len(word) > chunk_size:
            if current_words:
                pieces.append(" ".join(current_words))
                current_words = []
            start = 0
            step = max(1, chunk_size - overlap)
            while start < len(word):
                pieces.append(word[start : start + chunk_size])
                if start + chunk_size >= len(word):
                    break
                start += step
            continue
        if current_words and len(" ".join(current_words + [word])) > chunk_size:
            pieces.append(" ".join(current_words))
            overlap_words: list[str] = []
            overlap_length = 0
            for previous in reversed(current_words):
                added_length = len(previous) + (1 if overlap_words else 0)
                if overlap_length + added_length > overlap:
                    break
                overlap_words.insert(0, previous)
                overlap_length += added_length
            current_words = overlap_words + [word]
        else:
            current_words.append(word)
    if current_words:
        pieces.append(" ".join(current_words))
    return pieces


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()