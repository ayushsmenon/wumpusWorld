from unittest.mock import MagicMock
import pytest
from backend.assessment.generator import AssessmentGenerator
from backend.assessment.validator import AssessmentValidator


def test_validator_mcq_options_and_correct_answer():
    validator = AssessmentValidator()
    raw = {
        "question_type": "MCQ",
        "difficulty": "medium",
        "prompt": "Which algorithm finds the shortest path in unweighted graphs?",
        "options": ["DFS", "BFS", "Prim's", "Kruskal's"],
        "correct_answer": "BFS",
        "explanation": "BFS guarantees shortest path in unweighted graphs.",
    }
    is_valid, msg, cleaned = validator.validate_question(raw)
    assert is_valid is True
    assert cleaned["correct_answer"] == "BFS"
    assert len(cleaned["options"]) == 4


def test_validator_mcq_letter_mapping():
    validator = AssessmentValidator()
    raw = {
        "question_type": "MCQ",
        "difficulty": "easy",
        "prompt": "What data structure does DFS use?",
        "options": ["Queue", "Stack", "Heap", "Tree"],
        "correct_answer": "B",
    }
    is_valid, msg, cleaned = validator.validate_question(raw)
    assert is_valid is True
    assert cleaned["correct_answer"] == "Stack"


def test_validator_numerical_question():
    validator = AssessmentValidator()
    raw = {
        "question_type": "numerical",
        "difficulty": "hard",
        "prompt": "What is 2 to the power of 5?",
        "options": ["not needed"],
        "correct_answer": "32.0",
    }
    is_valid, msg, cleaned = validator.validate_question(raw)
    assert is_valid is True
    assert cleaned["correct_answer"] == "32"
    assert cleaned["options"] is None


def test_validator_short_answer_question():
    validator = AssessmentValidator()
    raw = {
        "question_type": "short_answer",
        "difficulty": "medium",
        "prompt": "Define a spanning tree in graph theory.",
        "correct_answer": "A subgraph that includes all vertices and is a tree.",
    }
    is_valid, msg, cleaned = validator.validate_question(raw)
    assert is_valid is True
    assert cleaned["options"] is None


def test_validator_rejects_malformed_mcq():
    validator = AssessmentValidator()
    raw = {
        "question_type": "MCQ",
        "difficulty": "medium",
        "prompt": "Invalid MCQ?",
        "options": ["Single Option"],
        "correct_answer": "Single Option",
    }
    is_valid, msg, _ = validator.validate_question(raw)
    assert is_valid is False
    assert "at least 2 options" in msg


def test_validator_grounding_rejection():
    validator = AssessmentValidator()
    raw = {
        "question_type": "MCQ",
        "difficulty": "medium",
        "prompt": "Who won the 1998 soccer world cup in Paris?",
        "options": ["Brazil", "France", "Italy", "Germany"],
        "correct_answer": "France",
    }
    context = "Photosynthesis is the biological process used by plants to convert light energy into chemical energy."
    is_valid, msg, _ = validator.validate_question(raw, context_text=context)
    assert is_valid is False
    assert "not grounded" in msg


def test_validator_verify_student_answer():
    validator = AssessmentValidator()
    mcq = {
        "question_type": "MCQ",
        "options": ["Queue", "Stack", "List"],
        "correct_answer": "Queue",
        "explanation": "BFS uses FIFO queue.",
    }
    is_cor, fb = validator.verify_student_answer(mcq, "Queue")
    assert is_cor is True
    assert "Correct!" in fb

    is_cor_letter, _ = validator.verify_student_answer(mcq, "A")
    assert is_cor_letter is True

    num_q = {
        "question_type": "numerical",
        "correct_answer": "42",
        "explanation": "Answer to life.",
    }
    is_cor_num, _ = validator.verify_student_answer(num_q, "42.0001")
    assert is_cor_num is True

    is_cor_wrong, _ = validator.verify_student_answer(num_q, "99")
    assert is_cor_wrong is False


def test_assessment_generator_generate_questions():
    fake_model = MagicMock()
    fake_response = MagicMock()
    fake_response.text = """[
        {
            "question_type": "MCQ",
            "difficulty": "medium",
            "prompt": "What data structure implements BFS traversal?",
            "options": ["Queue", "Stack", "Graph", "Set"],
            "correct_answer": "Queue",
            "explanation": "Queue preserves level-order FIFO discovery."
        }
    ]"""
    fake_model.generate_content.return_value = fake_response

    generator = AssessmentGenerator(model=fake_model)
    chunks = [
        {"chunk_text": "BFS uses a queue data structure to explore graphs.", "content_unit_id": 101}
    ]
    questions = generator.generate_questions("Graph Traversal", chunks, count=1)
    assert len(questions) == 1
    assert questions[0]["question_type"] == "MCQ"
    assert questions[0]["correct_answer"] == "Queue"
    assert questions[0]["content_unit_id"] == 101


def test_assessment_generator_create_adaptive_assessment():
    fake_cursor = MagicMock()
    fake_cursor.fetchone.side_effect = [
        {"mastery_score": 0.82},
        {"id": 5, "title": "Advanced Trees", "course_id": 1},
        [77],
        [501],
    ]
    fake_cursor.fetchall.side_effect = [
        [{"chunk_id": 1, "chunk_text": "AVL trees are height-balanced binary search trees.", "content_unit_id": 10, "filename": "trees.pdf", "page_number": 3, "slide_number": None}],
    ]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    fake_model = MagicMock()
    fake_response = MagicMock()
    fake_response.text = """[
        {
            "question_type": "MCQ",
            "difficulty": "hard",
            "prompt": "What is the balance factor condition in AVL trees?",
            "options": ["-1, 0, or 1", "Always 0", "At most 2", "Unconstrained"],
            "correct_answer": "-1, 0, or 1",
            "explanation": "An AVL tree maintains height balance where balance factor is in {-1, 0, 1}."
        }
    ]"""
    fake_model.generate_content.return_value = fake_response

    generator = AssessmentGenerator(
        connection_factory=lambda: fake_conn,
        model=fake_model,
    )

    result = generator.create_adaptive_assessment(student_id=1, topic_id=5, count=1)
    assert result["assessment_id"] == 77
    assert result["student_id"] == 1
    assert result["topic_id"] == 5
    assert len(result["questions"]) == 1
    assert result["questions"][0]["id"] == 501
    assert fake_conn.commit.called
