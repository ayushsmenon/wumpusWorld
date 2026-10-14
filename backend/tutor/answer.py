from contextlib import contextmanager
import os

os.environ["HF_HOME"] = os.getenv("HF_HOME", "D:/wumpus_cache")
import re
from collections.abc import Callable, Iterator, Sequence
from typing import Any

from backend.tutor.citations import build_context_and_citations, extract_cited_ids


OUT_OF_SCOPE_PHRASES = (
    "cannot find any course material",
    "not covered in the course material",
    "outside the scope",
    "does not cover",
    "do not cover",
    "not mentioned in the provided",
    "context does not contain",
    "not contain enough information",
    "no course material covering",
)


class SourceGroundedTutor:
    def __init__(
        self,
        db_url: str | None = None,
        api_key: str | None = None,
        embedding_provider: Any = None,
        model: Any = None,
        relevance_threshold: float = 0.25,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.relevance_threshold = relevance_threshold
        self._connection_factory = connection_factory
        self._embedding_provider = embedding_provider
        self._model = model

        if self.api_key and not self._model:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel("gemini-2.5-flash")
            except Exception:
                self._model = None

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self._connection_factory is not None:
            conn = self._connection_factory()
            try:
                yield conn
                if hasattr(conn, "commit"):
                    conn.commit()
            except Exception:
                if hasattr(conn, "rollback"):
                    conn.rollback()
                raise
            finally:
                if hasattr(conn, "close"):
                    conn.close()
            return

        if not self.db_url:
            raise RuntimeError("DATABASE_URL is not configured")

        try:
            from backend.database.connection import get_db_pool

            pool = get_db_pool(self.db_url)
            with pool.get_connection() as conn:
                yield conn
        except Exception:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _get_embedding_provider(self) -> Any:
        if self._embedding_provider is not None:
            return self._embedding_provider
        from backend.knowledge.embeddings import LocalSentenceTransformerProvider

        self._embedding_provider = LocalSentenceTransformerProvider(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            local_files_only=True,
            device="cpu",
        )
        return self._embedding_provider

    def embed_query(self, query: str) -> list[float]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must not be empty")
        provider = self._get_embedding_provider()
        if hasattr(provider, "embed_query"):
            return provider.embed_query(query)
        if hasattr(provider, "embed"):
            return provider.embed([query.strip()])[0]
        if hasattr(provider, "encode"):
            vector = provider.encode(
                query.strip(),
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return vector.tolist() if hasattr(vector, "tolist") else list(vector)
        raise RuntimeError("Configured embedding provider does not support query embedding")

    def retrieve_context(
        self,
        query_or_embedding: str | Sequence[float],
        course_id: str | int,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        if isinstance(query_or_embedding, str):
            query_embedding = self.embed_query(query_or_embedding)
        else:
            query_embedding = list(query_or_embedding)

        if not query_embedding:
            raise ValueError("Query embedding cannot be empty")

        course_str = str(course_id).strip()
        vector_literal = "[" + ",".join(str(float(val)) for val in query_embedding) + "]"

        sql = """
            SELECT 
                c.id AS chunk_id,
                c.chunk_text,
                c.embedding <=> %s::vector AS distance,
                1 - (c.embedding <=> %s::vector) AS similarity,
                cu.source_id,
                cu.file_id,
                cu.course_id,
                cu.filename,
                cu.source_type,
                cu.source_uri,
                cu.page_number,
                cu.slide_number,
                cu.video_timestamp,
                t.title AS topic_title
            FROM chunks c
            JOIN content_units cu ON c.content_unit_id = cu.id
            LEFT JOIN topics t ON cu.topic_id = t.id
            WHERE (cu.course_id = %s::text OR (t.course_id IS NOT NULL AND t.course_id::text = %s::text))
              AND c.embedding IS NOT NULL
              AND 1 - (c.embedding <=> %s::vector) >= %s
            ORDER BY c.embedding <=> %s::vector ASC
            LIMIT %s;
        """

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        vector_literal,
                        vector_literal,
                        course_str,
                        course_str,
                        vector_literal,
                        min_score,
                        vector_literal,
                        top_k,
                    ),
                )
                rows = cur.fetchall()
                results: list[dict[str, Any]] = []
                for row in rows:
                    if isinstance(row, dict):
                        results.append(row)
                    else:
                        results.append(dict(row))
                return results

    def generate_grounded_answer(
        self,
        student_query: str,
        course_id: str | int,
        query_embedding: Sequence[float] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        if not isinstance(student_query, str) or not student_query.strip():
            raise ValueError("Student query must not be empty")

        if query_embedding is None:
            embedding = self.embed_query(student_query)
        else:
            embedding = list(query_embedding)

        chunks = self.retrieve_context(
            query_or_embedding=embedding,
            course_id=course_id,
            top_k=top_k,
            min_score=self.relevance_threshold,
        )

        if not chunks:
            return {
                "answer": "I cannot find any course material covering this query.",
                "citations": [],
                "cited_citations": [],
                "is_grounded": False,
                "out_of_scope": True,
            }

        context_text, citations = build_context_and_citations(chunks)

        prompt = (
            "You are a source-grounded AI study companion for Track D: Personalized Tutoring & Adaptive Learning.\n"
            "Answer the student's question using ONLY the provided course context blocks below.\n"
            "Every factual statement must cite its source using bracketed numbers (e.g., [1], [2]).\n"
            "If the provided context does not contain enough information to answer the question, or if the question is out of scope, "
            "state clearly that the course materials do not cover this topic.\n"
            "Do not speculate or extrapolate beyond the provided context.\n\n"
            f"Context:\n{context_text}\n\n"
            f"Student Question: {student_query.strip()}"
        )

        model = self._model
        if model is None:
            if not self.api_key:
                raise RuntimeError("GEMINI_API_KEY is not configured and no model was provided")
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            self._model = model

        response = model.generate_content(prompt)
        answer_text = (
            response.text
            if hasattr(response, "text")
            else getattr(response, "content", str(response))
        )

        cited_ids = extract_cited_ids(answer_text)
        cited_citations = [c for c in citations if c["id"] in cited_ids]

        normalized_answer = answer_text.strip().lower()
        is_refusal = any(phrase in normalized_answer for phrase in OUT_OF_SCOPE_PHRASES)

        is_grounded = bool(cited_citations) and not is_refusal

        return {
            "answer": answer_text,
            "citations": citations,
            "cited_citations": cited_citations,
            "is_grounded": is_grounded,
            "out_of_scope": not is_grounded,
        }