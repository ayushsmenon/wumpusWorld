from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_courses_and_topics():
    res_courses = client.get("/courses")
    assert res_courses.status_code == 200
    assert isinstance(res_courses.json(), list)

    res_topics = client.get("/courses/1/topics")
    assert res_topics.status_code == 200
    assert isinstance(res_topics.json(), list)


def test_api_assessment_generate():
    with patch("backend.main.AssessmentGenerator") as MockGen:
        mock_instance = MockGen.return_value
        mock_instance.create_adaptive_assessment.return_value = {
            "assessment_id": 99,
            "student_id": 1,
            "topic_id": 2,
            "topic_title": "Graph Traversal",
            "assessment_type": "adaptive_quiz",
            "questions": [
                {
                    "id": 101,
                    "question_type": "MCQ",
                    "difficulty": "medium",
                    "prompt": "What does BFS use?",
                    "options": ["Queue", "Stack"],
                    "correct_answer": "Queue",
                    "explanation": "FIFO queue.",
                }
            ],
        }

        res = client.post(
            "/assessment/generate",
            json={"student_id": 1, "topic_id": 2, "count": 1},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["assessment_id"] == 99
        assert len(data["questions"]) == 1


def test_api_assessment_submit():
    with patch("backend.main.LearnerMasteryTracker") as MockTracker, \
         patch("backend.main.AssessmentValidator") as MockValidator:
        
        mock_tracker = MockTracker.return_value
        fake_conn = MagicMock()
        fake_cursor = MagicMock()
        fake_cursor.fetchone.return_value = {
            "id": 101,
            "topic_id": 2,
            "question_type": "MCQ",
            "difficulty": "medium",
            "prompt": "What does BFS use?",
            "options": ["Queue", "Stack"],
            "correct_answer": "Queue",
            "explanation": "FIFO queue.",
        }
        fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
        mock_tracker._connection.return_value.__enter__.return_value = fake_conn
        mock_tracker._get_connection.return_value = fake_conn

        mock_validator = MockValidator.return_value
        mock_validator.verify_student_answer.return_value = (True, "Correct! FIFO queue.")

        mock_mastery = MagicMock()
        mock_mastery.to_dict.return_value = {
            "student_id": 1,
            "topic_id": 2,
            "mastery_score": 0.65,
            "confidence": 0.35,
        }
        mock_tracker.record_answer_and_update.return_value = mock_mastery

        res = client.post(
            "/assessment/submit",
            json={
                "student_id": 1,
                "assessment_id": 99,
                "question_id": 101,
                "submitted_answer": "Queue",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_correct"] is True
        assert data["correct_answer"] == "Queue"
        assert data["updated_mastery"]["mastery_score"] == 0.65


def test_api_assessment_get():
    with patch("backend.main.LearnerMasteryTracker") as MockTracker:
        mock_tracker = MockTracker.return_value
        fake_conn = MagicMock()
        fake_cursor = MagicMock()
        fake_cursor.fetchone.return_value = {
            "id": 99,
            "student_id": 1,
            "assessment_type": "adaptive_quiz",
            "score": 100.0,
            "completed": True,
            "created_at": "2026-10-14T00:00:00",
        }
        fake_cursor.fetchall.return_value = [
            {
                "id": 101,
                "topic_id": 2,
                "question_type": "MCQ",
                "difficulty": "medium",
                "prompt": "What does BFS use?",
                "options": ["Queue", "Stack"],
                "correct_answer": "Queue",
                "explanation": "FIFO queue.",
            }
        ]
        fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
        mock_tracker._connection.return_value.__enter__.return_value = fake_conn

        res = client.get("/assessment/99")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == 99
        assert len(data["questions"]) == 1


def test_api_recommendations():
    with patch("backend.main.AdaptiveRecommendationEngine") as MockEngine:
        mock_engine = MockEngine.return_value
        mock_engine.suggest_study_path.return_value = [
            {"topic_id": 1, "title": "BFS", "status": "ready_to_learn", "priority": 1.2}
        ]
        mock_engine.identify_weak_topics.return_value = []
        mock_engine.recommend_next_topics.return_value = [
            {"topic_id": 1, "title": "BFS", "status": "ready_to_learn"}
        ]

        res = client.get("/learner/recommendations/1/10")
        assert res.status_code == 200
        data = res.json()
        assert len(data["study_path"]) == 1
        assert len(data["next_topics"]) == 1
