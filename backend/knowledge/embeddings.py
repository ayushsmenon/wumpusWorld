"""Replaceable embedding providers and validated batch embedding."""

from __future__ import annotations

import math
import os
import time
from collections.abc import Sequence
from typing import Protocol

from .contracts import KnowledgeChunk


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot return valid vectors."""


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class LocalModelError(EmbeddingError):
    """Raised when a local embedding model cannot be loaded."""


class LocalSentenceTransformerProvider:
    """Offline Sentence Transformers provider.

    The model must already exist in the local Hugging Face cache when
    ``local_files_only`` is true.
    """

    default_model = "sentence-transformers/all-MiniLM-L6-v2"
    dimensions = 384

    def __init__(
        self,
        model_name: str = default_model,
        cache_folder: str | None = None,
        local_files_only: bool = True,
        device: str = "cpu",
        model: object | None = None,
    ) -> None:
        self.model = model_name
        self.local_files_only = local_files_only
        self.device = device
        if model is not None:
            self._model = model
            return
        try:
            import os
            os.environ["HF_HOME"] = os.getenv("HF_HOME", "D:/wumpus_cache")
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise LocalModelError(
                "The sentence-transformers package is required for local embeddings"
            ) from exc
        try:
            effective_cache = cache_folder or os.getenv("EMBEDDING_CACHE_DIR") or None
            self._model = SentenceTransformer(
                model_name,
                cache_folder=effective_cache,
                local_files_only=local_files_only,
                device=device,
            )
        except Exception as exc:
            mode = "offline" if local_files_only else "local/download"
            raise LocalModelError(
                f"Embedding model '{model_name}' is unavailable in {mode} mode"
            ) from exc

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        normalized = [_normalize_text(text) for text in texts]
        if any(not text for text in normalized):
            raise EmbeddingError("Embedding input must not contain empty text")
        try:
            vectors = self._model.encode(
                normalized,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingError("Local embedding inference failed") from exc
        result = [vector.tolist() if hasattr(vector, "tolist") else list(vector) for vector in vectors]
        _validate_vectors(result, len(normalized), self.dimensions)
        return result


class OpenAIEmbeddingProvider:
    model = "text-embedding-3-small"
    dimensions = 1536

    def __init__(self, api_key: str | None = None, batch_size: int = 100, max_retries: int = 3) -> None:
        if batch_size <= 0 or max_retries < 0:
            raise ValueError("batch_size must be positive and max_retries must not be negative")
        self.batch_size = batch_size
        self.max_retries = max_retries
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise EmbeddingError("OPENAI_API_KEY is not configured")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EmbeddingError("The openai package is required for OpenAI embeddings") from exc
        self._client = OpenAI(api_key=key)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            for attempt in range(self.max_retries + 1):
                try:
                    response = self._client.embeddings.create(model=self.model, input=batch)
                    batch_vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
                    _validate_vectors(batch_vectors, len(batch), self.dimensions)
                    vectors.extend(batch_vectors)
                    break
                except Exception as exc:
                    if attempt == self.max_retries:
                        raise EmbeddingError("Embedding provider failed after retries") from exc
                    time.sleep(2**attempt)
        return vectors


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider
        self._cache: dict[tuple[str, str], list[float]] = {}

    def embed_chunks(self, chunks: Sequence[KnowledgeChunk]) -> dict[str, list[float]]:
        missing = [chunk for chunk in chunks if (chunk.content_hash, self.provider.model) not in self._cache]
        if missing:
            vectors = self.provider.embed([chunk.text for chunk in missing])
            _validate_vectors(vectors, len(missing), self.provider.dimensions)
            for chunk, vector in zip(missing, vectors):
                self._cache[(chunk.content_hash, self.provider.model)] = vector
        return {chunk.chunk_id: self._cache[(chunk.content_hash, self.provider.model)] for chunk in chunks}

    def embed_query(self, question: str) -> list[float]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question must not be empty")
        vectors = self.provider.embed([question.strip()])
        _validate_vectors(vectors, 1, self.provider.dimensions)
        return vectors[0]


def create_embedding_provider(
    provider_name: str | None = None,
    *,
    local_files_only: bool | None = None,
) -> EmbeddingProvider:
    """Create the configured provider without implicit paid-provider fallback."""
    selected = (provider_name or os.getenv("EMBEDDING_PROVIDER", "local")).strip().lower()
    if selected == "local":
        offline = _env_bool("EMBEDDING_LOCAL_FILES_ONLY", True) if local_files_only is None else local_files_only
        return LocalSentenceTransformerProvider(
            model_name=os.getenv("EMBEDDING_MODEL", LocalSentenceTransformerProvider.default_model),
            cache_folder=os.getenv("EMBEDDING_CACHE_DIR") or None,
            local_files_only=offline,
            device=os.getenv("EMBEDDING_DEVICE", "cpu"),
        )
    if selected == "openai":
        raise EmbeddingError(
            "OpenAI text-embedding-3-small returns 1536 dimensions and is incompatible "
            "with the configured 384-dimensional vector schema"
        )
    raise EmbeddingError(f"Unsupported embedding provider: {selected}")


def _normalize_text(text: str) -> str:
    if not isinstance(text, str):
        raise EmbeddingError("Embedding input must be text")
    return " ".join(text.split())


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _validate_vectors(vectors: Sequence[Sequence[float]], expected_count: int, dimensions: int) -> None:
    if len(vectors) != expected_count:
        raise EmbeddingError(f"Provider returned {len(vectors)} vectors for {expected_count} inputs")
    for vector in vectors:
        if len(vector) != dimensions or any(
            not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector
        ):
            raise EmbeddingError(f"Provider returned a vector with invalid dimension or values; expected {dimensions}")