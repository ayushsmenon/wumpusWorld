from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from backend.assessment.generator import AssessmentGenerator
from backend.assessment.validator import AssessmentValidator
from backend.database.connection import DatabasePool
from backend.learner.mastery import LearnerMasteryTracker, calculate_mastery_update
from backend.learner.recommendations import (
    AdaptiveRecommendationEngine,
    TopicMasteryInfo,
    TopicNode,
)
from backend.main import app
from backend.tutor.answer import SourceGroundedTutor
from backend.tutor.citations import (
    build_context_and_citations,
    extract_cited_ids,
    format_citation_label,
    format_source_location,
    format_timestamp,
)


client = TestClient(app)


def test_audit_database_pool_lifecycle():
    with patch("psycopg2.pool.ThreadedConnectionPool") as MockPool:
        mock_raw_pool = MockPool.return_value
        fake_conn = MagicMock()
        mock_raw_pool.getconn.return_value = fake_conn
        mock_raw_pool.closed = False

        DatabasePool.reset_instance()
        db_pool = DatabasePool.get_instance(db_url="postgresql://usr:pwd@localhost:5432/wumpus")

        with db_pool.get_connection() as conn:
            assert conn == fake_conn

        assert fake_conn.commit.called
        assert mock_raw_pool.putconn.called

        db_pool.close()
        assert mock_raw_pool.closeall.called
        DatabasePool.reset_instance()


def test_audit_database_pool_rollback_on_exception():
    with patch("psycopg2.pool.ThreadedConnectionPool") as MockPool:
        mock_raw_pool = MockPool.return_value
        fake_conn = MagicMock()
        mock_raw_pool.getconn.return_value = fake_conn

        DatabasePool.reset_instance()
        db_pool = DatabasePool.get_instance(db_url="postgresql://usr:pwd@localhost:5432/wumpus")

        with pytest.raises(RuntimeError):
            with db_pool.get_connection():
                raise RuntimeError("Database error simulated")

        assert fake_conn.rollback.called
        assert mock_raw_pool.putconn.called
        DatabasePool.reset_instance()


def test_audit_citations_formatting():
    assert format_timestamp(3670) == "01:01:10"
    assert format_timestamp(45) == "00:45"
    assert format_source_location(page_number=12) == "Page 12"
    assert format_source_location(slide_number=5) == "Slide 5"
    assert format_source_location(video_timestamp=135) == "Timestamp 02:15"
    assert format_source_location(source_type="pdf") == "Document"

    label = format_citation_label(filename="guide.pdf", page_number=4, topic_title="Graph Search")
    assert label == "guide.pdf - Page 4 [Graph Search]"

    context, citations = build_context_and_citations(
        [
            {"chunk_text": "BFS runs in linear time.", "page_number": 1, "filename": "doc.pdf"},
            {"chunk_text": "DFS uses a stack.", "slide_number": 2, "filename": "slides.pptx"},
        ]
    )
    assert "[1] BFS runs in linear time." in context
    assert "[2] DFS uses a stack." in context
    assert len(citations) == 2
    assert extract_cited_ids("According to [1] and [2], BFS and DFS differ.") == [1, 2]


def test_audit_tutor_cosine_distance_and_refusal():
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = []
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    tutor = SourceGroundedTutor(connection_factory=lambda: fake_conn)
    result = tutor.generate_grounded_answer(
        student_query="Explain baking bread.",
        course_id="1",
        query_embedding=[0.01] * 384,
    )
    assert result["is_grounded"] is False
    assert result["out_of_scope"] is True
    assert "cannot find any course material" in result["answer"].lower()


def test_audit_assessment_validation_and_grading():
    validator = AssessmentValidator()
    mcq = {
        "question_type": "MCQ",
        "difficulty": "medium",
        "prompt": "Which algorithm is complete for finite graphs?",
        "options": ["BFS", "DFS", "Random walk", "None"],
        "correct_answer": "BFS",
        "explanation": "BFS explores layer by layer.",
    }
    is_valid, msg, cleaned = validator.validate_question(mcq)
    assert is_valid is True
    assert cleaned["correct_answer"] == "BFS"

    is_correct, fb = validator.verify_student_answer(cleaned, "BFS")
    assert is_correct is True
    assert "Correct!" in fb

    is_wrong, fb_w = validator.verify_student_answer(cleaned, "DFS")
    assert is_wrong is False
    assert "Incorrect" in fb_w

    num_q = {
        "question_type": "numerical",
        "difficulty": "hard",
        "prompt": "Calculate 5 factorial.",
        "options": None,
        "correct_answer": "120",
        "explanation": "5! = 120",
    }
    is_v_num, _, c_num = validator.validate_question(num_q)
    assert is_v_num is True
    assert c_num["correct_answer"] == "120"
    is_cor_num, _ = validator.verify_student_answer(c_num, "120.00001")
    assert is_cor_num is True


def test_audit_learner_mastery_adaptive_updates():
    m1, c1 = calculate_mastery_update(0.5, 0.2, is_correct=True, difficulty="hard")
    assert m1 > 0.5
    assert c1 > 0.2

    m2, c2 = calculate_mastery_update(0.8, 0.5, is_correct=False, difficulty="easy")
    assert m2 < 0.8
    assert c2 > 0.5


def test_audit_recommendation_dag_ordering_and_weak_topics():
    engine = AdaptiveRecommendationEngine()
    topics = {
        1: TopicNode(id=1, course_id=1, title="Foundations", order_index=1, prerequisites=[]),
        2: TopicNode(id=2, course_id=1, title="Algorithms", order_index=2, prerequisites=[1]),
        3: TopicNode(id=3, course_id=1, title="Advanced Search", order_index=3, prerequisites=[2]),
    }
    masteries = {
        1: TopicMasteryInfo(topic_id=1, mastery_score=0.9, confidence=0.8),
        2: TopicMasteryInfo(topic_id=2, mastery_score=0.35, confidence=0.6),
    }

    order = engine.topological_sort(topics)
    assert order == [1, 2, 3]

    study_path = engine.compute_study_path(topics, masteries, target_topic_id=3)
    status_map = {item["topic_id"]: item["status"] for item in study_path}
    assert status_map[1] == "mastered"
    assert status_map[2] == "remediation"
    assert status_map[3] == "blocked"

    weak = engine.analyze_weak_topics(topics, masteries, mastery_threshold=0.7)
    assert len(weak) == 1
    assert weak[0]["topic_id"] == 2
    assert weak[0]["deficit"] > 0


def test_audit_api_endpoints_integrity():
    res_h = client.get("/health")
    assert res_h.status_code == 200

    res_c = client.get("/courses")
    assert res_c.status_code == 200
    assert len(res_c.json()) >= 1

    res_t = client.get("/courses/1/topics")
    assert res_t.status_code == 200
    assert len(res_t.json()) >= 1
