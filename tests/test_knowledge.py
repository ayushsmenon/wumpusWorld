from dataclasses import dataclass

import pytest

from backend.knowledge.chunking import TextChunker
from backend.knowledge.contracts import ContentRecord, RetrievalResult
from backend.knowledge.embeddings import EmbeddingError, EmbeddingService
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
