from contextlib import contextmanager
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
import os
from typing import Any


DIFFICULTY_WEIGHTS = {
    "easy": 0.75,
    "medium": 1.0,
    "hard": 1.25,
}


def calculate_mastery_update(
    current_mastery: float,
    current_confidence: float,
    is_correct: bool,
    difficulty: str = "medium",
) -> tuple[float, float]:
    weight = DIFFICULTY_WEIGHTS.get(difficulty.lower(), 1.0)
    current_m = max(0.0, min(1.0, float(current_mastery)))
    current_c = max(0.0, min(1.0, float(current_confidence)))

    if is_correct:
        gain = 0.20 * (1.0 - current_m) * weight
        new_mastery = current_m + gain
    else:
        loss = 0.15 * current_m * (1.0 / weight)
        new_mastery = current_m - loss

    confidence_gain = 0.15 * (1.0 - current_c)
    new_confidence = current_c + confidence_gain

    clamped_mastery = max(0.0, min(1.0, round(new_mastery, 4)))
    clamped_confidence = max(0.0, min(1.0, round(new_confidence, 4)))
    return clamped_mastery, clamped_confidence


@dataclass(frozen=True)
class TopicMastery:
    student_id: int
    topic_id: int
    mastery_score: float
    confidence: float
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LearnerMasteryTracker:
    def __init__(
        self,
        db_url: str | None = None,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self._connection_factory = connection_factory

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self._connection_factory is not None:
            conn = self._connection_factory()
            try:
                yield conn
                if hasattr(conn, "commit"):
                    conn.commit()
            except Exception:
                if hasattr(conn, "rollback"):
                    conn.rollback()
                raise
            finally:
                if hasattr(conn, "close"):
                    conn.close()
            return

        if not self.db_url:
            raise RuntimeError("DATABASE_URL is not configured")

        try:
            from backend.database.connection import get_db_pool

            pool = get_db_pool(self.db_url)
            with pool.get_connection() as conn:
                yield conn
        except Exception:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def get_topic_mastery(self, student_id: int, topic_id: int) -> TopicMastery:
        sql = """
            SELECT student_id, topic_id, mastery_score, confidence, updated_at
            FROM learner_mastery
            WHERE student_id = %s AND topic_id = %s;
        """
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (student_id, topic_id))
                row = cur.fetchone()
                if not row:
                    return TopicMastery(
                        student_id=student_id,
                        topic_id=topic_id,
                        mastery_score=0.0,
                        confidence=0.0,
                    )
                data = row if isinstance(row, dict) else dict(row)
                return TopicMastery(
                    student_id=data["student_id"],
                    topic_id=data["topic_id"],
                    mastery_score=float(data["mastery_score"]),
                    confidence=float(data["confidence"]),
                    updated_at=str(data.get("updated_at")),
                )

    def get_student_masteries(
        self,
        student_id: int,
        course_id: int | None = None,
    ) -> list[TopicMastery]:
        if course_id is not None:
            sql = """
                SELECT lm.student_id, lm.topic_id, lm.mastery_score, lm.confidence, lm.updated_at
                FROM learner_mastery lm
                JOIN topics t ON lm.topic_id = t.id
                WHERE lm.student_id = %s AND t.course_id = %s
                ORDER BY lm.topic_id ASC;
            """
            params: tuple[Any, ...] = (student_id, course_id)
        else:
            sql = """
                SELECT student_id, topic_id, mastery_score, confidence, updated_at
                FROM learner_mastery
                WHERE student_id = %s
                ORDER BY topic_id ASC;
            """
            params = (student_id,)

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                results = []
                for row in rows:
                    data = row if isinstance(row, dict) else dict(row)
                    results.append(
                        TopicMastery(
                            student_id=data["student_id"],
                            topic_id=data["topic_id"],
                            mastery_score=float(data["mastery_score"]),
                            confidence=float(data["confidence"]),
                            updated_at=str(data.get("updated_at")),
                        )
                    )
                return results

    def update_topic_mastery(
        self,
        student_id: int,
        topic_id: int,
        is_correct: bool,
        difficulty: str = "medium",
    ) -> TopicMastery:
        current = self.get_topic_mastery(student_id, topic_id)
        new_mastery, new_confidence = calculate_mastery_update(
            current_mastery=current.mastery_score,
            current_confidence=current.confidence,
            is_correct=is_correct,
            difficulty=difficulty,
        )

        upsert_sql = """
            INSERT INTO learner_mastery (student_id, topic_id, mastery_score, confidence, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (student_id, topic_id)
            DO UPDATE SET
                mastery_score = EXCLUDED.mastery_score,
                confidence = EXCLUDED.confidence,
                updated_at = CURRENT_TIMESTAMP
            RETURNING student_id, topic_id, mastery_score, confidence, updated_at;
        """

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    upsert_sql,
                    (student_id, topic_id, new_mastery, new_confidence),
                )
                row = cur.fetchone()
                data = row if isinstance(row, dict) else dict(row)
                return TopicMastery(
                    student_id=data["student_id"],
                    topic_id=data["topic_id"],
                    mastery_score=float(data["mastery_score"]),
                    confidence=float(data["confidence"]),
                    updated_at=str(data.get("updated_at")),
                )

    def record_answer_and_update(
        self,
        student_id: int,
        assessment_id: int,
        question_id: int,
        submitted_answer: str,
        is_correct: bool,
        feedback: str | None = None,
        misconception_detected: str | None = None,
    ) -> TopicMastery:
        with self._connection() as conn:
            with conn.cursor() as cur:
                answer_sql = """
                    INSERT INTO student_answers
                        (assessment_id, question_id, student_id, submitted_answer, is_correct, feedback, misconception_detected)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (student_id, assessment_id, question_id)
                    DO UPDATE SET
                        submitted_answer = EXCLUDED.submitted_answer,
                        is_correct = EXCLUDED.is_correct,
                        feedback = EXCLUDED.feedback,
                        misconception_detected = EXCLUDED.misconception_detected,
                        created_at = CURRENT_TIMESTAMP;
                """
                cur.execute(
                    answer_sql,
                    (
                        assessment_id,
                        question_id,
                        student_id,
                        submitted_answer,
                        is_correct,
                        feedback,
                        misconception_detected,
                    ),
                )

                cur.execute(
                    "SELECT topic_id, difficulty FROM questions WHERE id = %s;",
                    (question_id,),
                )
                q_row = cur.fetchone()
                if not q_row:
                    raise ValueError(f"Question {question_id} not found")
                q_data = q_row if isinstance(q_row, dict) else dict(q_row)
                topic_id = q_data["topic_id"]
                difficulty = q_data.get("difficulty") or "medium"

                cur.execute(
                    "SELECT mastery_score, confidence FROM learner_mastery WHERE student_id = %s AND topic_id = %s;",
                    (student_id, topic_id),
                )
                m_row = cur.fetchone()
                if m_row:
                    m_data = m_row if isinstance(m_row, dict) else dict(m_row)
                    current_m = float(m_data["mastery_score"])
                    current_c = float(m_data["confidence"])
                else:
                    current_m, current_c = 0.0, 0.0

                new_m, new_c = calculate_mastery_update(
                    current_mastery=current_m,
                    current_confidence=current_c,
                    is_correct=is_correct,
                    difficulty=difficulty,
                )

                upsert_sql = """
                    INSERT INTO learner_mastery (student_id, topic_id, mastery_score, confidence, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (student_id, topic_id)
                    DO UPDATE SET
                        mastery_score = EXCLUDED.mastery_score,
                        confidence = EXCLUDED.confidence,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING student_id, topic_id, mastery_score, confidence, updated_at;
                """
                cur.execute(upsert_sql, (student_id, topic_id, new_m, new_c))
                res_row = cur.fetchone()
                res_data = res_row if isinstance(res_row, dict) else dict(res_row)
                return TopicMastery(
                    student_id=res_data["student_id"],
                    topic_id=res_data["topic_id"],
                    mastery_score=float(res_data["mastery_score"]),
                    confidence=float(res_data["confidence"]),
                    updated_at=str(res_data.get("updated_at")),
                )

    def batch_update_from_assessment(
        self,
        student_id: int,
        assessment_id: int,
    ) -> dict[int, TopicMastery]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                sql = """
                    SELECT sa.question_id, sa.is_correct, q.topic_id, q.difficulty
                    FROM student_answers sa
                    JOIN questions q ON sa.question_id = q.id
                    WHERE sa.student_id = %s AND sa.assessment_id = %s
                    ORDER BY sa.created_at ASC;
                """
                cur.execute(sql, (student_id, assessment_id))
                rows = cur.fetchall()

        updated_masteries: dict[int, TopicMastery] = {}
        for row in rows:
            data = row if isinstance(row, dict) else dict(row)
            topic_id = data["topic_id"]
            is_correct = bool(data["is_correct"])
            difficulty = data.get("difficulty") or "medium"
            updated = self.update_topic_mastery(
                student_id=student_id,
                topic_id=topic_id,
                is_correct=is_correct,
                difficulty=difficulty,
            )
            updated_masteries[topic_id] = updated
        return updated_masteries
