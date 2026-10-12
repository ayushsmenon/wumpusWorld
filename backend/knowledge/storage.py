"""PostgreSQL/pgvector persistence for indexed knowledge."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import contextmanager
import os
from collections import defaultdict
from typing import Any, Iterator

from .contracts import KnowledgeChunk, RetrievalResult


class StorageError(RuntimeError):
    """Raised when knowledge cannot be persisted or searched."""


class PostgresKnowledgeStore:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    @classmethod
    def from_environment(cls) -> "PostgresKnowledgeStore":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise StorageError("DATABASE_URL is not configured")
        try:
            import psycopg
        except ImportError as exc:
            raise StorageError("The psycopg package is required for PostgreSQL storage") from exc
        return cls(lambda: psycopg.connect(database_url))

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        connection = self._connection_factory()
        try:
            yield connection
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise StorageError("Knowledge storage operation failed") from exc
        finally:
            connection.close()

    def index_document(
        self,
        chunks: Sequence[KnowledgeChunk],
        embeddings: dict[str, Sequence[float]],
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        if not chunks:
            raise ValueError("Cannot index an empty document; use delete_document for removal")
        if any(chunk.chunk_id not in embeddings for chunk in chunks):
            raise ValueError("An embedding is missing for one or more chunks")
        first = chunks[0]
        if any(chunk.file_id != first.file_id or chunk.course_id != first.course_id for chunk in chunks):
            raise ValueError("index_document accepts chunks from one file and course at a time")

        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM content_units WHERE course_id = %s AND file_id = %s",
                    (first.course_id, first.file_id),
                )
                chunks_by_source: dict[str, list[KnowledgeChunk]] = defaultdict(list)
                for chunk in chunks:
                    chunks_by_source[chunk.source_id].append(chunk)
                for source_chunks in chunks_by_source.values():
                    source = source_chunks[0]
                    cursor.execute(
                    """
                    INSERT INTO content_units
                        (source_id, file_id, course_id, filename, source_type, source_uri,
                         page_number, slide_number, content_text, content_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        source.source_id,
                        source.file_id,
                        source.course_id,
                        source.filename,
                        source.source_type,
                        source.source_uri,
                        source.page_number,
                        source.slide_number,
                        "\n\n".join(chunk.text for chunk in source_chunks),
                        _document_hash(source_chunks),
                    ),
                    )
                    content_unit_id = cursor.fetchone()[0]
                    for chunk in source_chunks:
                        metadata = _metadata(chunk)
                        metadata["chunk_id"] = chunk.chunk_id
                        cursor.execute(
                            """
                            INSERT INTO chunks
                                (content_unit_id, chunk_index, chunk_text, embedding,
                                 content_hash, embedding_model, metadata)
                            VALUES (%s, %s, %s, %s::vector, %s, %s, %s)
                            """,
                            (
                                content_unit_id,
                                chunk.chunk_index,
                                chunk.text,
                                _vector_literal(embeddings[chunk.chunk_id]),
                                chunk.content_hash,
                                embedding_model,
                                metadata,
                            ),
                        )

    def delete_document(self, course_id: str, file_id: str) -> None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM content_units WHERE course_id = %s AND file_id = %s",
                    (course_id, file_id),
                )

    def search(
        self,
        course_id: str,
        query_embedding: Sequence[float],
        limit: int,
        min_score: float,
    ) -> list[RetrievalResult]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(c.metadata->>'chunk_id', c.id::text), c.chunk_text,
                           1 - (c.embedding <=> %s::vector) AS score,
                           u.source_id, u.file_id, u.course_id, u.filename, u.source_uri,
                           u.page_number, u.slide_number,
                           COALESCE(c.metadata->>'section_title', '') AS section_title,
                           c.metadata
                    FROM chunks c
                    JOIN content_units u ON u.id = c.content_unit_id
                    WHERE u.course_id = %s
                      AND 1 - (c.embedding <=> %s::vector) >= %s
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (
                        _vector_literal(query_embedding),
                        course_id,
                        _vector_literal(query_embedding),
                        min_score,
                        _vector_literal(query_embedding),
                        limit,
                    ),
                )
                return [_result_from_row(row) for row in cursor.fetchall()]


def _vector_literal(vector: Sequence[float]) -> str:
    if not vector:
        raise ValueError("Embedding vector must not be empty")
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def _document_hash(chunks: Sequence[KnowledgeChunk]) -> str:
    import hashlib

    return hashlib.sha256("".join(chunk.content_hash for chunk in chunks).encode("ascii")).hexdigest()


def _metadata(chunk: KnowledgeChunk) -> dict[str, Any]:
    return {
        **dict(chunk.metadata),
        "chunk_id": chunk.chunk_id,
        "section_title": chunk.section_title,
        "source_type": chunk.source_type,
    }


def _result_from_row(row: Sequence[Any]) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=str(row[0]),
        text=row[1],
        score=float(row[2]),
        source_id=row[3],
        file_id=row[4],
        course_id=row[5],
        filename=row[6],
        source_uri=row[7],
        page_number=row[8],
        slide_number=row[9],
        section_title=row[10] or None,
        metadata=row[11] or {},
    )
