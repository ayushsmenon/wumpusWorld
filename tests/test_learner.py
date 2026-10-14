from unittest.mock import MagicMock
import pytest
from backend.learner.mastery import (
    LearnerMasteryTracker,
    TopicMastery,
    calculate_mastery_update,
)
from backend.learner.recommendations import (
    AdaptiveRecommendationEngine,
    TopicMasteryInfo,
    TopicNode,
)


def test_calculate_mastery_update_gains():
    m0, c0 = 0.5, 0.2
    m_correct_med, c_correct_med = calculate_mastery_update(m0, c0, True, "medium")
    assert m_correct_med > m0
    assert c_correct_med > c0

    m_correct_hard, _ = calculate_mastery_update(m0, c0, True, "hard")
    m_correct_easy, _ = calculate_mastery_update(m0, c0, True, "easy")
    assert m_correct_hard > m_correct_med > m_correct_easy


def test_calculate_mastery_update_penalties():
    m0, c0 = 0.8, 0.4
    m_wrong_med, c_wrong_med = calculate_mastery_update(m0, c0, False, "medium")
    assert m_wrong_med < m0
    assert c_wrong_med > c0

    m_wrong_easy, _ = calculate_mastery_update(m0, c0, False, "easy")
    m_wrong_hard, _ = calculate_mastery_update(m0, c0, False, "hard")
    assert m_wrong_easy < m_wrong_med < m_wrong_hard


def test_calculate_mastery_update_boundaries():
    m_high, c_high = calculate_mastery_update(0.99, 0.99, True, "hard")
    assert 0.0 <= m_high <= 1.0
    assert 0.0 <= c_high <= 1.0

    m_low, c_low = calculate_mastery_update(0.01, 0.05, False, "easy")
    assert 0.0 <= m_low <= 1.0
    assert 0.0 <= c_low <= 1.0


def test_tracker_get_unseen_topic_mastery():
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = None
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    tracker = LearnerMasteryTracker(connection_factory=lambda: fake_conn)
    tm = tracker.get_topic_mastery(student_id=1, topic_id=99)
    assert tm.student_id == 1
    assert tm.topic_id == 99
    assert tm.mastery_score == 0.0
    assert tm.confidence == 0.0


def test_tracker_update_topic_mastery():
    fake_cursor = MagicMock()
    fake_cursor.fetchone.side_effect = [
        {"student_id": 1, "topic_id": 5, "mastery_score": 0.4, "confidence": 0.2, "updated_at": "t1"},
        {"student_id": 1, "topic_id": 5, "mastery_score": 0.52, "confidence": 0.32, "updated_at": "t2"},
    ]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    tracker = LearnerMasteryTracker(connection_factory=lambda: fake_conn)
    updated = tracker.update_topic_mastery(student_id=1, topic_id=5, is_correct=True, difficulty="medium")
    assert updated.mastery_score == 0.52
    assert updated.confidence == 0.32
    assert fake_conn.commit.called


def test_tracker_record_answer_and_update():
    fake_cursor = MagicMock()
    fake_cursor.fetchone.side_effect = [
        {"topic_id": 10, "difficulty": "hard"},
        {"mastery_score": 0.3, "confidence": 0.1},
        {"student_id": 2, "topic_id": 10, "mastery_score": 0.475, "confidence": 0.235, "updated_at": "t3"},
    ]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    tracker = LearnerMasteryTracker(connection_factory=lambda: fake_conn)
    res = tracker.record_answer_and_update(
        student_id=2,
        assessment_id=1,
        question_id=101,
        submitted_answer="Option B",
        is_correct=True,
    )
    assert res.topic_id == 10
    assert res.mastery_score == 0.475
    assert fake_conn.commit.called


def test_recommendation_topological_sort():
    engine = AdaptiveRecommendationEngine()
    topics = {
        1: TopicNode(id=1, course_id=10, title="Arrays", order_index=1, prerequisites=[]),
        2: TopicNode(id=2, course_id=10, title="Linked Lists", order_index=2, prerequisites=[1]),
        3: TopicNode(id=3, course_id=10, title="Trees", order_index=3, prerequisites=[2]),
        4: TopicNode(id=4, course_id=10, title="Graphs", order_index=4, prerequisites=[2, 3]),
    }
    order = engine.topological_sort(topics)
    assert order.index(1) < order.index(2)
    assert order.index(2) < order.index(3)
    assert order.index(3) < order.index(4)


def test_recommendation_weak_topics_root_cause_analysis():
    engine = AdaptiveRecommendationEngine()
    topics = {
        1: TopicNode(id=1, course_id=1, title="Basic Math", order_index=1, prerequisites=[]),
        2: TopicNode(id=2, course_id=1, title="Calculus I", order_index=2, prerequisites=[1]),
        3: TopicNode(id=3, course_id=1, title="Calculus II", order_index=3, prerequisites=[2]),
    }
    masteries = {
        1: TopicMasteryInfo(topic_id=1, mastery_score=0.45, confidence=0.8),
        2: TopicMasteryInfo(topic_id=2, mastery_score=0.30, confidence=0.7),
        3: TopicMasteryInfo(topic_id=3, mastery_score=0.20, confidence=0.5),
    }

    weak = engine.analyze_weak_topics(topics, masteries, mastery_threshold=0.70)
    assert len(weak) == 3

    calc2 = next(item for item in weak if item["topic_id"] == 3)
    assert len(calc2["root_cause_prerequisites"]) == 1
    assert calc2["root_cause_prerequisites"][0]["prerequisite_id"] == 2

    basic_math = next(item for item in weak if item["topic_id"] == 1)
    assert len(basic_math["root_cause_prerequisites"]) == 0
    assert basic_math["priority"] > 0


def test_recommendation_study_path_prerequisites_progression():
    engine = AdaptiveRecommendationEngine()
    topics = {
        1: TopicNode(id=1, course_id=1, title="Python Basics", order_index=1, prerequisites=[]),
        2: TopicNode(id=2, course_id=1, title="Data Structures", order_index=2, prerequisites=[1]),
        3: TopicNode(id=3, course_id=1, title="Algorithms", order_index=3, prerequisites=[2]),
    }

    masteries = {
        1: TopicMasteryInfo(topic_id=1, mastery_score=0.85, confidence=0.9),
        2: TopicMasteryInfo(topic_id=2, mastery_score=0.40, confidence=0.6),
    }

    path = engine.compute_study_path(topics, masteries, target_topic_id=None, mastery_threshold=0.70)
    status_by_id = {item["topic_id"]: item["status"] for item in path}

    assert status_by_id[1] == "mastered"
    assert status_by_id[2] == "remediation"
    assert status_by_id[3] == "blocked"

    ds_item = next(item for item in path if item["topic_id"] == 2)
    assert len(ds_item["blocking_prerequisites"]) == 0

    algo_item = next(item for item in path if item["topic_id"] == 3)
    assert len(algo_item["blocking_prerequisites"]) == 1
    assert algo_item["blocking_prerequisites"][0]["topic_id"] == 2


def test_recommend_next_topics():
    engine = AdaptiveRecommendationEngine()
    topics = {
        1: TopicNode(id=1, course_id=1, title="Intro", order_index=1, prerequisites=[]),
        2: TopicNode(id=2, course_id=1, title="Intermediate", order_index=2, prerequisites=[1]),
        3: TopicNode(id=3, course_id=1, title="Advanced", order_index=3, prerequisites=[2]),
    }
    masteries = {
        1: TopicMasteryInfo(topic_id=1, mastery_score=0.95, confidence=0.9),
    }

    class MockEngine(AdaptiveRecommendationEngine):
        def load_course_topics(self, cid):
            return topics

        def load_student_masteries(self, sid, cid):
            return masteries

    rec_engine = MockEngine()
    next_topics = rec_engine.recommend_next_topics(student_id=10, course_id=1, limit=2)
    assert len(next_topics) == 2
    assert next_topics[0]["topic_id"] == 2
    assert next_topics[0]["status"] == "ready_to_learn"
    assert next_topics[1]["topic_id"] == 3
    assert next_topics[1]["status"] == "blocked"
