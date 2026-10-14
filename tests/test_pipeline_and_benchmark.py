from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from backend.evaluation.benchmark import (
    SystemEvaluator,
    calculate_answer_relevancy,
    calculate_context_precision,
    calculate_context_recall,
    calculate_faithfulness,
)
from backend.knowledge.contracts import ContentRecord
from backend.knowledge.pipeline import KnowledgePipeline
from backend.main import app

client = TestClient(app)


def test_benchmark_metric_calculations():
    prec = calculate_context_precision([1, 2, 3], [1, 3])
    assert 0.0 <= prec <= 1.0

    rec = calculate_context_recall([1, 2], [1, 2, 3])
    assert abs(rec - (2 / 3)) < 1e-4

    faith = calculate_faithfulness("Answer text citing [1] and [2].", [{"id": 1}, {"id": 2}])
    assert faith == 1.0

    rel = calculate_answer_relevancy("Breadth-first search uses a queue.", ["queue", "breadth"])
    assert rel == 1.0


def test_evaluator_rag_and_personalization():
    evaluator = SystemEvaluator()
    rag_res = evaluator.run_rag_evaluation()
    assert "faithfulness" in rag_res
    assert "answer_relevancy" in rag_res
    assert "context_precision" in rag_res
    assert "context_recall" in rag_res
    assert "out_of_scope_refusal_accuracy" in rag_res

    sim_res = evaluator.run_personalization_simulation(sessions_per_profile=3)
    assert "profiles" in sim_res
    assert "question_repetition_rate" in sim_res
    assert "average_mastery_gain" in sim_res
    assert len(sim_res["profiles"]) == 3


def test_api_create_course_endpoint():
    with patch("backend.main.get_db_pool") as MockPool:
        mock_pool = MockPool.return_value
        fake_conn = MagicMock()
        fake_cur = MagicMock()
        fake_cur.fetchone.return_value = {"id": 10, "title": "Quantum Computing", "description": "Intro"}
        fake_cur.fetchall.return_value = [{"id": 20, "title": "Foundations"}]
        fake_cur.__enter__.return_value = fake_cur
        fake_conn.cursor.return_value.__enter__.return_value = fake_cur
        mock_pool.get_cursor.return_value.__enter__.return_value = fake_cur

        res = client.post("/courses", json={"title": "Quantum Computing", "subject": "Physics"})
        assert res.status_code == 200
        data = res.json()
        assert "course" in data
        assert "topics" in data


def test_api_diagnostic_endpoint():
    with patch("backend.main.AssessmentGenerator") as MockGen:
        mock_gen = MockGen.return_value
        mock_gen.create_adaptive_assessment.return_value = {
            "assessment_id": 50,
            "student_id": 1,
            "topic_id": 1,
            "assessment_type": "diagnostic_exam",
            "questions": [],
        }

        res = client.post("/learner/diagnostic", json={"student_id": 1, "course_id": 1})
        assert res.status_code == 200
        data = res.json()
        assert data["assessment_id"] == 50


def test_api_benchmark_endpoint():
    with patch("backend.main.SystemEvaluator") as MockEval:
        mock_eval = MockEval.return_value
        mock_eval.run_rag_evaluation.return_value = {"faithfulness": 0.95}
        mock_eval.run_personalization_simulation.return_value = {"average_mastery_gain": 0.35}

        res = client.get("/evaluation/benchmark")
        assert res.status_code == 200
        data = res.json()
        assert "rag_evaluation" in data
        assert "personalization_simulation" in data


def test_knowledge_pipeline_flow(tmp_path):
    test_file = tmp_path / "notes.txt"
    test_file.write_text("Dijkstra algorithm finds shortest paths in graphs.", encoding="utf-8")

    fake_store = MagicMock()
    fake_embedder = MagicMock()
    fake_embedder.embed.return_value = [[0.05] * 384]

    pipeline = KnowledgePipeline(store=fake_store, embedder=fake_embedder)

    with patch.dict("backend.knowledge.pipeline.PARSERS", {
        ".txt": ("pdf", lambda p, out: [MagicMock(text=p.read_text(), unit_type="page", number=1, notes="", has_visuals=False, tables=[], images=[], start_sec=None, metadata={})])
    }):
        result = pipeline.ingest_and_index(test_file, course_id="cs101")
        assert result["status"] == "indexed"
        assert result["units_count"] == 1
        assert fake_store.index_document.called
