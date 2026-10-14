from unittest.mock import MagicMock
import pytest
from backend.tutor.citations import (
    build_context_and_citations,
    create_citation,
    extract_cited_ids,
    format_citation_label,
    format_citation_marker,
    format_source_location,
    format_timestamp,
)
from backend.tutor.answer import SourceGroundedTutor


def test_format_timestamp():
    assert format_timestamp(None) == ""
    assert format_timestamp(-5) == ""
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(45) == "00:45"
    assert format_timestamp(125.4) == "02:05"
    assert format_timestamp(3665) == "01:01:05"


def test_format_source_location():
    assert format_source_location(page_number=4) == "Page 4"
    assert format_source_location(slide_number=12) == "Slide 12"
    assert format_source_location(video_timestamp=75) == "Timestamp 01:15"
    assert format_source_location(source_type="pdf") == "Document"
    assert format_source_location(source_type="pptx") == "Slide"
    assert format_source_location(source_type="video") == "Video"
    assert format_source_location() == "Source"


def test_format_citation_label():
    label_page = format_citation_label(filename="notes.pdf", page_number=7)
    assert label_page == "notes.pdf - Page 7"

    label_slide = format_citation_label(filename="deck.pptx", slide_number=3, topic_title="Graphs")
    assert label_slide == "deck.pptx - Slide 3 [Graphs]"

    label_video = format_citation_label(filename="lecture.mp4", video_timestamp=190)
    assert label_video == "lecture.mp4 - Timestamp 03:10"

    assert format_citation_label() == "Source"


def test_build_context_and_citations():
    chunks = [
        {
            "chunk_text": "Breadth-first search traverses level by level.",
            "source_type": "pdf",
            "filename": "algorithms.pdf",
            "page_number": 15,
            "topic_title": "Graph Traversal",
        },
        {
            "chunk_text": "Depth-first search uses a stack.",
            "source_type": "pptx",
            "filename": "traversal.pptx",
            "slide_number": 8,
            "topic_title": "Graph Traversal",
        },
    ]
    context, citations = build_context_and_citations(chunks)
    assert "[1] Breadth-first search" in context
    assert "[2] Depth-first search" in context
    assert len(citations) == 2
    assert citations[0]["id"] == 1
    assert citations[0]["location"] == "Page 15"
    assert citations[1]["id"] == 2
    assert citations[1]["location"] == "Slide 8"


def test_extract_cited_ids():
    text = "BFS explores broadly [1], whereas DFS delves deep [2]. Multiple claims point to [1] and [3]."
    cited = extract_cited_ids(text)
    assert cited == [1, 2, 3]
    assert extract_cited_ids("") == []
    assert extract_cited_ids("No brackets here.") == []


def test_tutor_embed_query_local():
    tutor = SourceGroundedTutor(db_url="postgresql://test:test@localhost:5432/test")
    vector = tutor.embed_query("What is Dijkstra's algorithm?")
    assert isinstance(vector, list)
    assert len(vector) == 384
    assert all(isinstance(v, float) for v in vector)

    with pytest.raises(ValueError):
        tutor.embed_query("   ")


def test_tutor_retrieval_and_cosine_distance_query():
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = [
        {
            "chunk_id": 1,
            "chunk_text": "A spanning tree connects all vertices.",
            "distance": 0.12,
            "similarity": 0.88,
            "source_id": "unit-1",
            "file_id": "file-1",
            "course_id": "cs101",
            "filename": "graphs.pdf",
            "source_type": "pdf",
            "source_uri": "uri",
            "page_number": 42,
            "slide_number": None,
            "video_timestamp": None,
            "topic_title": "Spanning Trees",
        }
    ]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    tutor = SourceGroundedTutor(connection_factory=lambda: fake_conn)
    results = tutor.retrieve_context(
        query_or_embedding=[0.1] * 384,
        course_id="cs101",
        top_k=3,
        min_score=0.5,
    )
    assert len(results) == 1
    assert results[0]["chunk_id"] == 1
    assert results[0]["page_number"] == 42
    assert fake_cursor.execute.called


def test_tutor_declines_out_of_scope_query_when_no_chunks():
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = []
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    tutor = SourceGroundedTutor(connection_factory=lambda: fake_conn)
    result = tutor.generate_grounded_answer(
        student_query="How to make pizza dough?",
        course_id="cs101",
        query_embedding=[0.0] * 384,
    )
    assert result["is_grounded"] is False
    assert result["out_of_scope"] is True
    assert "cannot find any course material" in result["answer"].lower()
    assert result["citations"] == []


def test_tutor_grounded_answer_generation():
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = [
        {
            "chunk_id": 10,
            "chunk_text": "Binary search has O(log n) time complexity.",
            "distance": 0.08,
            "similarity": 0.92,
            "source_id": "u-1",
            "file_id": "f-1",
            "course_id": "cs101",
            "filename": "search.pdf",
            "source_type": "pdf",
            "source_uri": None,
            "page_number": 5,
            "slide_number": None,
            "video_timestamp": None,
            "topic_title": "Searching",
        }
    ]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    fake_model = MagicMock()
    fake_response = MagicMock()
    fake_response.text = "Binary search runs in logarithmic time O(log n) [1]."
    fake_model.generate_content.return_value = fake_response

    tutor = SourceGroundedTutor(
        connection_factory=lambda: fake_conn,
        model=fake_model,
    )

    res = tutor.generate_grounded_answer(
        student_query="What is the complexity of binary search?",
        course_id="cs101",
        query_embedding=[0.05] * 384,
    )
    assert res["is_grounded"] is True
    assert res["out_of_scope"] is False
    assert len(res["citations"]) == 1
    assert len(res["cited_citations"]) == 1
    assert res["cited_citations"][0]["id"] == 1
    assert "Binary search runs in logarithmic time" in res["answer"]


def test_tutor_refusal_response_marked_ungrounded():
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = [
        {
            "chunk_id": 1,
            "chunk_text": "Irrelevant text about sorting algorithms.",
            "distance": 0.70,
            "similarity": 0.30,
            "source_id": "u-1",
            "file_id": "f-1",
            "course_id": "cs101",
            "filename": "sorting.pdf",
            "source_type": "pdf",
            "source_uri": None,
            "page_number": 1,
            "slide_number": None,
            "video_timestamp": None,
            "topic_title": "Sorting",
        }
    ]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    fake_model = MagicMock()
    fake_response = MagicMock()
    fake_response.text = "This topic is outside the scope of the provided course material."
    fake_model.generate_content.return_value = fake_response

    tutor = SourceGroundedTutor(
        connection_factory=lambda: fake_conn,
        model=fake_model,
        relevance_threshold=0.20,
    )

    res = tutor.generate_grounded_answer(
        student_query="Explain quantum computing.",
        course_id="cs101",
        query_embedding=[0.01] * 384,
    )
    assert res["is_grounded"] is False
    assert res["out_of_scope"] is True
