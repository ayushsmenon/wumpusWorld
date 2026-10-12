from dataclasses import dataclass

import pytest

from backend.knowledge.chunking import TextChunker
from backend.knowledge.contracts import ContentRecord, RetrievalResult
from backend.knowledge.embeddings import (
    EmbeddingError,
    EmbeddingService,
    LocalModelError,
    LocalSentenceTransformerProvider,
    create_embedding_provider,
)
from backend.knowledge.retrieval import RetrievalService


def record(text: str = "Introduction.\n\nA second paragraph explains the topic.") -> ContentRecord:
    return ContentRecord(
        source_id="page-1",
        file_id="file-7",
        course_id="course-2",
        filename="notes.pdf",
        text=text,
        source_type="pdf",
        source_uri="s3://materials/notes.pdf",
        page_number=3,
        section_title="Introduction",
        metadata={"author": "student"},
    )


def test_chunking_preserves_source_metadata_and_empty_input():
    chunks = TextChunker(chunk_size=30, overlap=5, min_chunk_size=0).chunk(record("One sentence. Another sentence."))

    assert len(chunks) == 2
    assert all(chunk.course_id == "course-2" for chunk in chunks)
    assert all(chunk.file_id == "file-7" for chunk in chunks)
    assert chunks[0].page_number == 3
    assert chunks[0].metadata["author"] == "student"
    assert TextChunker().chunk(record("")) == []


def test_chunking_enforces_size_and_overlaps_long_sections():
    text = " ".join(f"word{i}" for i in range(80))
    chunks = TextChunker(chunk_size=60, overlap=10, min_chunk_size=0).chunk(record(text))

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 60 for chunk in chunks)
    assert any(
        set(chunks[index].text.split()) & set(chunks[index + 1].text.split())
        for index in range(len(chunks) - 1)
    )


def test_chunking_rejects_malformed_records():
    with pytest.raises(ValueError, match="Missing required"):
        TextChunker().chunk(ContentRecord("", "file", "course", "x.pdf", "text", "pdf"))
    with pytest.raises(ValueError, match="text must be a string"):
        TextChunker().chunk(ContentRecord("source", "file", "course", "x.pptx", None, "pptx"))


@dataclass
class FakeProvider:
    calls: int = 0
    model: str = "fake"
    dimensions: int = 3

    def embed(self, texts):
        self.calls += 1
        return [[float(index + 1)] * self.dimensions for index in range(len(texts))]


def test_embedding_service_batches_and_caches_unchanged_chunks():
    provider = FakeProvider()
    service = EmbeddingService(provider)
    chunks = TextChunker(min_chunk_size=0).chunk(record("A short source."))

    first = service.embed_chunks(chunks)
    second = service.embed_chunks(chunks)

    assert first == second
    assert provider.calls == 1
    assert len(service.embed_query("What is this?")) == 3


def test_embedding_service_rejects_invalid_provider_response():
    class InvalidProvider(FakeProvider):
        def embed(self, texts):
            return [[1.0]]

    with pytest.raises(EmbeddingError, match="invalid dimension"):
        EmbeddingService(InvalidProvider()).embed_query("question")


class FakeVector:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class FakeSentenceTransformer:
    def __init__(self):
        self.inputs = []

    def encode(self, texts, **kwargs):
        self.inputs.append((texts, kwargs))
        return [FakeVector([0.25] * 384) for _ in texts]


def test_local_provider_returns_normalized_384_dimensional_vectors():
    model = FakeSentenceTransformer()
    provider = LocalSentenceTransformerProvider(model=model)

    vectors = provider.embed(["  A document\nwith whitespace.  ", "A query"])

    assert provider.model == "sentence-transformers/all-MiniLM-L6-v2"
    assert len(vectors) == 2
    assert all(len(vector) == 384 for vector in vectors)
    assert all(isinstance(value, float) for value in vectors[0])
    assert model.inputs[0][0] == ["A document with whitespace.", "A query"]
    assert model.inputs[0][1]["normalize_embeddings"] is True


def test_local_provider_rejects_empty_text_and_handles_unicode_consistently():
    provider = LocalSentenceTransformerProvider(model=FakeSentenceTransformer())

    with pytest.raises(EmbeddingError, match="empty"):
        provider.embed(["   "])

    first = provider.embed(["Café — velocity"])
    second = provider.embed(["Café — velocity"])
    assert first == second


def test_local_provider_defaults_to_cpu_and_loads_model_once():
    model = FakeSentenceTransformer()
    provider = LocalSentenceTransformerProvider(model=model)

    provider.embed(["document"])

    assert provider.device == "cpu"
    assert len(model.inputs) == 1


def test_local_provider_reports_missing_model(monkeypatch):
    class MissingSentenceTransformer:
        def __init__(self, *args, **kwargs):
            raise OSError("model missing")

    class FakeSentenceTransformersModule:
        SentenceTransformer = MissingSentenceTransformer

    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", FakeSentenceTransformersModule())

    with pytest.raises(LocalModelError, match="unavailable"):
        LocalSentenceTransformerProvider(local_files_only=True)


def test_provider_factory_rejects_unknown_provider_without_fallback():
    with pytest.raises(EmbeddingError, match="Unsupported"):
        create_embedding_provider("unknown")
    with pytest.raises(EmbeddingError, match="incompatible"):
        create_embedding_provider("openai")


def test_storage_rejects_incompatible_vectors():
    from backend.knowledge.storage import PostgresKnowledgeStore

    chunk = TextChunker(min_chunk_size=0).chunk(record("content"))[0]
    store = PostgresKnowledgeStore(lambda: None)

    with pytest.raises(ValueError, match="384 dimensions"):
        store.index_document([chunk], {chunk.chunk_id: [0.0] * 1536})


class FakeStore:
    def __init__(self):
        self.course_ids = []

    def search(self, course_id, query_embedding, limit, min_score):
        self.course_ids.append(course_id)
        return [
            RetrievalResult(
                chunk_id="file-7:page-1:0",
                text="evidence",
                score=0.9,
                source_id="page-1",
                file_id="file-7",
                course_id=course_id,
                filename="notes.pdf",
                page_number=3,
            )
        ][:limit]


def test_retrieval_passes_course_filter_and_returns_structured_evidence():
    provider = FakeProvider()
    store = FakeStore()
    service = RetrievalService(EmbeddingService(provider), store, default_limit=2)

    results = service.retrieve("question", "course-2")

    assert store.course_ids == ["course-2"]
    assert results[0].filename == "notes.pdf"
    assert results[0].page_number == 3


def test_retrieval_controlled_ranking_and_course_isolation():
    class SemanticProvider(FakeProvider):
        model = "local-test"
        dimensions = 3

        def embed(self, texts):
            self.calls += 1
            vectors = []
            for text in texts:
                lowered = text.lower()
                vectors.append(
                    [1.0, 0.0, 0.0] if "photo" in lowered else
                    [0.0, 1.0, 0.0] if "binary" in lowered else
                    [0.0, 0.0, 1.0]
                )
            return vectors

    class RankingStore:
        rows = [
            RetrievalResult("a", "Photosynthesis converts light energy.", 0, "s-a", "f-a", "course-a", "biology.pdf", page_number=2),
            RetrievalResult("b", "Binary search halves a sorted interval.", 0, "s-b", "f-b", "course-a", "algorithms.pdf", page_number=8),
            RetrievalResult("c", "Photosynthesis from another course.", 0, "s-c", "f-c", "course-b", "other.pdf", page_number=1),
        ]

        def search(self, course_id, query_embedding, limit, min_score):
            candidates = [row for row in self.rows if row.course_id == course_id]
            def score(row):
                return 0.95 if row.chunk_id == "a" and query_embedding[0] else 0.95 if row.chunk_id == "b" and query_embedding[1] else 0.1
            return [RetrievalResult(**{**row.__dict__, "score": score(row)}) for row in sorted(candidates, key=score, reverse=True) if score(row) >= min_score][:limit]

    service = RetrievalService(EmbeddingService(SemanticProvider()), RankingStore(), min_score=0.5)
    results = service.retrieve("How does photosynthesis work?", "course-a")

    assert [result.chunk_id for result in results] == ["a"]
    assert all(result.course_id == "course-a" for result in results)


def test_retrieval_validates_course_and_question():
    service = RetrievalService(EmbeddingService(FakeProvider()), FakeStore())
    with pytest.raises(ValueError, match="course_id"):
        service.retrieve("question", "")
    with pytest.raises(ValueError, match="Question"):
        service.retrieve("", "course-2")


def test_complete_local_pipeline_preserves_slide_citation():
    source = ContentRecord(
        source_id="slide-4",
        file_id="deck-1",
        course_id="course-3",
        filename="physics.pptx",
        text="Kinematics describes motion and velocity.",
        source_type="pptx",
        slide_number=4,
    )
    chunks = TextChunker(min_chunk_size=0).chunk(source)
    provider = FakeProvider()
    embeddings = EmbeddingService(provider)
    vectors = embeddings.embed_chunks(chunks)

    class LocalStore:
        def search(self, course_id, query_embedding, limit, min_score):
            return [
                RetrievalResult(
                    chunk_id=chunks[0].chunk_id,
                    text=chunks[0].text,
                    score=0.95,
                    source_id=chunks[0].source_id,
                    file_id=chunks[0].file_id,
                    course_id=course_id,
                    filename=chunks[0].filename,
                    slide_number=chunks[0].slide_number,
                )
            ][:limit]

    results = RetrievalService(embeddings, LocalStore()).retrieve("What is velocity?", "course-3")

    assert vectors[chunks[0].chunk_id]
    assert results[0].filename == "physics.pptx"
    assert results[0].slide_number == 4
