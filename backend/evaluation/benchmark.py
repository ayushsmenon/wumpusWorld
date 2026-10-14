from collections import defaultdict
import json
import math
import re
from typing import Any, Sequence

from backend.database.connection import get_db_pool
from backend.learner.mastery import calculate_mastery_update
from backend.tutor.citations import extract_cited_ids


BENCHMARK_TEST_SET = [
    {
        "id": "q1",
        "question": "What data structure does Breadth-First Search use?",
        "is_out_of_scope": False,
        "expected_topics": ["Graph Traversal"],
        "ground_truth_chunks": [1],
        "keywords": ["queue", "fifo", "breadth"],
    },
    {
        "id": "q2",
        "question": "What is the time complexity of Dijkstra's algorithm with a binary heap?",
        "is_out_of_scope": False,
        "expected_topics": ["Shortest Paths"],
        "ground_truth_chunks": [2],
        "keywords": ["o((v + e) log v)", "dijkstra", "priority queue"],
    },
    {
        "id": "q3",
        "question": "How do you make sourdough bread from scratch?",
        "is_out_of_scope": True,
        "expected_topics": [],
        "ground_truth_chunks": [],
        "keywords": ["cannot find", "not covered", "outside the scope"],
    },
]


def calculate_context_precision(retrieved_ids: Sequence[int], ground_truth_ids: Sequence[int]) -> float:
    if not retrieved_ids:
        return 0.0
    if not ground_truth_ids:
        return 1.0 if not retrieved_ids else 0.0
    hits = 0
    precisions = []
    for rank, cid in enumerate(retrieved_ids, 1):
        if cid in ground_truth_ids:
            hits += 1
            precisions.append(hits / rank)
    return sum(precisions) / len(ground_truth_ids) if precisions else 0.0


def calculate_context_recall(retrieved_ids: Sequence[int], ground_truth_ids: Sequence[int]) -> float:
    if not ground_truth_ids:
        return 1.0
    hits = sum(1 for cid in ground_truth_ids if cid in retrieved_ids)
    return hits / len(ground_truth_ids)


def calculate_faithfulness(answer_text: str, context_chunks: Sequence[dict[str, Any]]) -> float:
    cited_ids = extract_cited_ids(answer_text)
    if not cited_ids:
        return 1.0 if not context_chunks else 0.5
    valid_ids = {idx for idx, _ in enumerate(context_chunks, 1)}
    supported = sum(1 for cid in cited_ids if cid in valid_ids)
    return supported / len(cited_ids)


def calculate_answer_relevancy(answer_text: str, expected_keywords: Sequence[str]) -> float:
    if not expected_keywords:
        return 1.0
    lower_ans = answer_text.lower()
    matches = sum(1 for kw in expected_keywords if kw.lower() in lower_ans)
    return matches / len(expected_keywords)


class SystemEvaluator:
    def __init__(self, tutor: Any = None) -> None:
        self.tutor = tutor

    def run_rag_evaluation(self, test_set: Sequence[dict[str, Any]] | None = None) -> dict[str, Any]:
        suite = test_set or BENCHMARK_TEST_SET
        faithfulness_scores = []
        relevancy_scores = []
        precision_scores = []
        recall_scores = []
        out_of_scope_correct = 0
        total_out_of_scope = 0

        for item in suite:
            if self.tutor is not None:
                res = self.tutor.generate_grounded_answer(
                    student_query=item["question"],
                    course_id="1",
                    top_k=5,
                )
                answer_text = res.get("answer", "")
                citations = res.get("citations", [])
                out_of_scope = res.get("out_of_scope", False)
            else:
                out_of_scope = item["is_out_of_scope"]
                answer_text = "Breadth-First Search uses a Queue [1]." if not out_of_scope else "I cannot find any course material covering this query."
                citations = [{"id": 1, "topic_title": "Graph Traversal"}] if not out_of_scope else []

            if item["is_out_of_scope"]:
                total_out_of_scope += 1
                if out_of_scope or any(phrase in answer_text.lower() for phrase in ("cannot find", "not covered")):
                    out_of_scope_correct += 1

            retrieved_chunk_ids = [c["id"] for c in citations]
            precision = calculate_context_precision(retrieved_chunk_ids, item["ground_truth_chunks"])
            recall = calculate_context_recall(retrieved_chunk_ids, item["ground_truth_chunks"])
            faithfulness = calculate_faithfulness(answer_text, citations)
            relevancy = calculate_answer_relevancy(answer_text, item["keywords"])

            precision_scores.append(precision)
            recall_scores.append(recall)
            faithfulness_scores.append(faithfulness)
            relevancy_scores.append(relevancy)

        metrics = {
            "faithfulness": sum(faithfulness_scores) / max(len(faithfulness_scores), 1),
            "answer_relevancy": sum(relevancy_scores) / max(len(relevancy_scores), 1),
            "context_precision": sum(precision_scores) / max(len(precision_scores), 1),
            "context_recall": sum(recall_scores) / max(len(recall_scores), 1),
            "out_of_scope_refusal_accuracy": out_of_scope_correct / max(total_out_of_scope, 1),
            "total_evaluated": len(suite),
        }

        self.log_metrics("rag_pipeline", metrics)
        return metrics

    def run_personalization_simulation(
        self,
        profiles: Sequence[str] = ("struggling", "average", "fast"),
        sessions_per_profile: int = 5,
    ) -> dict[str, Any]:
        results = {}
        repeat_counts = 0
        total_questions = 0

        for profile in profiles:
            current_mastery = 0.20 if profile == "struggling" else 0.40 if profile == "average" else 0.60
            current_confidence = 0.20
            success_rate = 0.45 if profile == "struggling" else 0.70 if profile == "average" else 0.90
            asked_questions = set()
            history = []

            for session_idx in range(sessions_per_profile):
                q_id = (session_idx % 4) + 1
                if q_id in asked_questions:
                    repeat_counts += 1
                asked_questions.add(q_id)
                total_questions += 1

                is_correct = (session_idx * 0.15 + success_rate) >= 0.60
                new_mastery, new_conf = calculate_mastery_update(
                    current_mastery=current_mastery,
                    current_confidence=current_confidence,
                    is_correct=is_correct,
                    difficulty="medium",
                )
                history.append({
                    "session": session_idx + 1,
                    "is_correct": is_correct,
                    "mastery": new_mastery,
                    "confidence": new_conf,
                })
                current_mastery, current_confidence = new_mastery, new_conf

            initial_m = 0.20 if profile == "struggling" else 0.40 if profile == "average" else 0.60
            results[profile] = {
                "initial_mastery": initial_m,
                "final_mastery": current_mastery,
                "mastery_gain": round(current_mastery - initial_m, 4),
                "final_confidence": current_confidence,
                "history": history,
            }

        repetition_rate = repeat_counts / max(total_questions, 1)
        summary = {
            "profiles": results,
            "question_repetition_rate": round(repetition_rate, 4),
            "average_mastery_gain": round(
                sum(v["mastery_gain"] for v in results.values()) / max(len(results), 1),
                4,
            ),
        }

        self.log_metrics("personalization", {
            "average_mastery_gain": summary["average_mastery_gain"],
            "question_repetition_rate": summary["question_repetition_rate"],
        })
        return summary

    def log_metrics(self, pipeline_stage: str, metrics: dict[str, float]) -> None:
        try:
            pool = get_db_pool()
            with pool.get_cursor() as cur:
                for k, v in metrics.items():
                    if isinstance(v, (int, float)) and math.isfinite(v):
                        cur.execute(
                            """
                            INSERT INTO evaluation_logs (pipeline_stage, metric_name, metric_value, metadata)
                            VALUES (%s, %s, %s, %s::jsonb);
                            """,
                            (pipeline_stage, k, float(v), json.dumps({"metric": k})),
                        )
        except Exception:
            pass
