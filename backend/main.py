from typing import Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.assessment.generator import AssessmentGenerator
from backend.assessment.validator import AssessmentValidator
from backend.database.connection import get_db_pool
from backend.learner.mastery import LearnerMasteryTracker
from backend.learner.recommendations import AdaptiveRecommendationEngine
from backend.tutor.answer import SourceGroundedTutor

app = FastAPI(title="Wumpus World Tutor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str
    course_id: str
    top_k: int = 5


class RecordAnswerRequest(BaseModel):
    student_id: int
    assessment_id: int
    question_id: int
    submitted_answer: str
    is_correct: bool
    feedback: Optional[str] = None
    misconception_detected: Optional[str] = None


class TopicMasteryUpdateRequest(BaseModel):
    student_id: int
    topic_id: int
    is_correct: bool
    difficulty: str = "medium"


class GenerateAssessmentRequest(BaseModel):
    student_id: int
    topic_id: int
    assessment_type: str = "adaptive_quiz"
    count: int = 3
    target_difficulty: Optional[str] = None


class SubmitAssessmentAnswerRequest(BaseModel):
    student_id: int
    assessment_id: int
    question_id: int
    submitted_answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/courses")
def list_courses():
    try:
        pool = get_db_pool()
        with pool.get_cursor() as cur:
            cur.execute("SELECT id, title, description, created_at FROM courses ORDER BY id ASC;")
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return [
            {
                "id": 1,
                "title": "Data Structures & Algorithms",
                "description": "Master foundational and advanced data structures, graph traversals, and shortest path algorithms.",
            },
            {
                "id": 2,
                "title": "Artificial Intelligence & Search",
                "description": "Explore heuristic search, state-space exploration, and adaptive agent reasoning.",
            },
        ]


@app.get("/courses/{course_id}/topics")
def list_topics(course_id: int):
    try:
        pool = get_db_pool()
        with pool.get_cursor() as cur:
            cur.execute(
                "SELECT id, course_id, parent_id, title, description, order_index FROM topics WHERE course_id = %s ORDER BY order_index ASC, id ASC;",
                (course_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return [
            {"id": 1, "course_id": course_id, "title": "Graph Traversal", "order_index": 1},
            {"id": 2, "course_id": course_id, "title": "Shortest Paths", "order_index": 2},
            {"id": 3, "course_id": course_id, "title": "Spanning Trees", "order_index": 3},
        ]


@app.post("/tutor/ask")
def tutor_ask(payload: AskRequest):
    try:
        tutor = SourceGroundedTutor()
        return tutor.generate_grounded_answer(
            student_query=payload.query,
            course_id=payload.course_id,
            top_k=payload.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/learner/mastery/{student_id}")
def get_masteries(student_id: int, course_id: Optional[int] = None):
    try:
        tracker = LearnerMasteryTracker()
        masteries = tracker.get_student_masteries(student_id=student_id, course_id=course_id)
        return [m.to_dict() for m in masteries]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/learner/mastery/answer")
def record_quiz_answer(payload: RecordAnswerRequest):
    try:
        tracker = LearnerMasteryTracker()
        updated = tracker.record_answer_and_update(
            student_id=payload.student_id,
            assessment_id=payload.assessment_id,
            question_id=payload.question_id,
            submitted_answer=payload.submitted_answer,
            is_correct=payload.is_correct,
            feedback=payload.feedback,
            misconception_detected=payload.misconception_detected,
        )
        return updated.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/learner/mastery/update")
def update_topic_mastery(payload: TopicMasteryUpdateRequest):
    try:
        tracker = LearnerMasteryTracker()
        updated = tracker.update_topic_mastery(
            student_id=payload.student_id,
            topic_id=payload.topic_id,
            is_correct=payload.is_correct,
            difficulty=payload.difficulty,
        )
        return updated.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/learner/recommendations/{student_id}/{course_id}")
def get_recommendations(student_id: int, course_id: int, target_topic_id: Optional[int] = None):
    try:
        engine = AdaptiveRecommendationEngine()
        study_path = engine.suggest_study_path(
            student_id=student_id,
            course_id=course_id,
            target_topic_id=target_topic_id,
        )
        weak_topics = engine.identify_weak_topics(
            student_id=student_id,
            course_id=course_id,
        )
        next_topics = engine.recommend_next_topics(
            student_id=student_id,
            course_id=course_id,
        )
        return {
            "study_path": study_path,
            "weak_topics": weak_topics,
            "next_topics": next_topics,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/assessment/generate")
def generate_assessment(payload: GenerateAssessmentRequest):
    try:
        generator = AssessmentGenerator()
        return generator.create_adaptive_assessment(
            student_id=payload.student_id,
            topic_id=payload.topic_id,
            assessment_type=payload.assessment_type,
            count=payload.count,
            target_difficulty=payload.target_difficulty,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/assessment/{assessment_id}")
def get_assessment(assessment_id: int):
    try:
        tracker = LearnerMasteryTracker()
        with tracker._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, student_id, assessment_type, score, completed, created_at FROM assessments WHERE id = %s;",
                    (assessment_id,),
                )
                a_row = cur.fetchone()
                if not a_row:
                    raise HTTPException(status_code=404, detail="Assessment not found")
                a_data = a_row if isinstance(a_row, dict) else dict(a_row)

                cur.execute(
                    """
                    SELECT q.id, q.topic_id, q.question_type, q.difficulty, q.prompt, q.options, q.correct_answer, q.explanation
                    FROM questions q
                    JOIN assessment_questions aq ON q.id = aq.question_id
                    WHERE aq.assessment_id = %s
                    ORDER BY q.id ASC;
                    """,
                    (assessment_id,),
                )
                q_rows = cur.fetchall()
                a_data["questions"] = [dict(r) if not isinstance(r, dict) else r for r in q_rows]
                return a_data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/assessment/submit")
def submit_assessment_answer(payload: SubmitAssessmentAnswerRequest):
    try:
        tracker = LearnerMasteryTracker()
        validator = AssessmentValidator()

        with tracker._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, topic_id, question_type, difficulty, prompt, options, correct_answer, explanation FROM questions WHERE id = %s;",
                    (payload.question_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Question not found")
                q_data = row if isinstance(row, dict) else dict(row)

        is_correct, feedback = validator.verify_student_answer(q_data, payload.submitted_answer)
        updated_mastery = tracker.record_answer_and_update(
            student_id=payload.student_id,
            assessment_id=payload.assessment_id,
            question_id=payload.question_id,
            submitted_answer=payload.submitted_answer,
            is_correct=is_correct,
            feedback=feedback,
        )

        return {
            "is_correct": is_correct,
            "feedback": feedback,
            "correct_answer": q_data["correct_answer"],
            "explanation": q_data.get("explanation"),
            "updated_mastery": updated_mastery.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
