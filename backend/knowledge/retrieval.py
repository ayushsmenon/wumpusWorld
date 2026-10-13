"""Course-scoped retrieval service independent of UI frameworks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .contracts import RetrievalResult
from .embeddings import EmbeddingService


class VectorStore(Protocol):
    def search(self, course_id: str, query_embedding: Sequence[float], limit: int, min_score: float) -> list[RetrievalResult]:
        ...


class RetrievalService:
    def __init__(
        self,
        embeddings: EmbeddingService,
        store: VectorStore,
        default_limit: int = 5,
        min_score: float = 0.0,
    ) -> None:
        if default_limit <= 0:
            raise ValueError("default_limit must be positive")
        self.embeddings = embeddings
        self.store = store
        self.default_limit = default_limit
        self.min_score = min_score

    def retrieve(self, question: str, course_id: str, limit: int | None = None) -> list[RetrievalResult]:
        if not isinstance(course_id, str) or not course_id.strip():
            raise ValueError("course_id must not be empty")
        requested_limit = limit if limit is not None else self.default_limit
        if requested_limit <= 0:
            raise ValueError("limit must be positive")
        query_embedding = self.embeddings.embed_query(question)
        return self.store.search(course_id.strip(), query_embedding, requested_limit, self.min_score)