import json
import os
import re
from collections.abc import Callable
from typing import Any, Sequence

from backend.assessment.validator import AssessmentValidator


class AssessmentGenerator:
    def __init__(
        self,
        db_url: str | None = None,
        api_key: str | None = None,
        model: Any = None,
        validator: AssessmentValidator | None = None,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.validator = validator or AssessmentValidator()
        self._connection_factory = connection_factory
        self._model = model

        if self.api_key and not self._model:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel("gemini-2.5-flash")
            except Exception:
                self._model = None

    def _get_connection(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        if not self.db_url:
            raise RuntimeError("DATABASE_URL is not configured")
        try:
            import psycopg
            from psycopg.rows import dict_row

            return psycopg.connect(self.db_url, row_factory=dict_row)
        except ImportError:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)

    def get_topic_chunks(self, topic_id: int, limit: int = 5) -> tuple[str, list[dict[str, Any]]]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, course_id FROM topics WHERE id = %s;",
                    (topic_id,),
                )
                topic_row = cur.fetchone()
                if not topic_row:
                    raise ValueError(f"Topic {topic_id} not found")
                t_data = topic_row if isinstance(topic_row, dict) else dict(topic_row)
                topic_title = t_data["title"]
                course_id = t_data["course_id"]

                sql = """
                    SELECT c.id AS chunk_id, c.chunk_text, cu.id AS content_unit_id,
                           cu.filename, cu.page_number, cu.slide_number
                    FROM chunks c
                    JOIN content_units cu ON c.content_unit_id = cu.id
                    WHERE cu.topic_id = %s
                    LIMIT %s;
                """
                cur.execute(sql, (topic_id, limit))
                rows = cur.fetchall()

                if not rows:
                    fallback_sql = """
                        SELECT c.id AS chunk_id, c.chunk_text, cu.id AS content_unit_id,
                               cu.filename, cu.page_number, cu.slide_number
                        FROM chunks c
                        JOIN content_units cu ON c.content_unit_id = cu.id
                        WHERE cu.course_id = %s::text
                        LIMIT %s;
                    """
                    cur.execute(fallback_sql, (str(course_id), limit))
                    rows = cur.fetchall()

                chunks: list[dict[str, Any]] = []
                for row in rows:
                    chunks.append(row if isinstance(row, dict) else dict(row))
                return topic_title, chunks
        finally:
            conn.close()

    def generate_questions(
        self,
        topic_title: str,
        chunks: Sequence[dict[str, Any]],
        count: int = 3,
        target_difficulty: str = "medium",
    ) -> list[dict[str, Any]]:
        if not chunks:
            return []

        context_blocks = []
        for idx, chunk in enumerate(chunks, start=1):
            text = chunk.get("chunk_text") or ""
            context_blocks.append(f"[{idx}] {text}")
        context_text = "\n\n".join(context_blocks)

        prompt = (
            "You are an expert educational assessment creator for Track D: Personalized Tutoring & Adaptive Learning.\n"
            f"Generate exactly {count} assessment questions strictly grounded in the course material for the topic: '{topic_title}'.\n"
            f"Target difficulty level: {target_difficulty}.\n"
            "Include a diverse mix of question types across MCQ (with 4 distinct options), short_answer, and numerical.\n"
            "Output ONLY a raw valid JSON array of question objects without markdown ticks or backticks.\n"
            "Each object must follow this exact schema:\n"
            "[\n"
            "  {\n"
            '    "question_type": "MCQ",\n'
            f'    "difficulty": "{target_difficulty}",\n'
            '    "prompt": "Clear question text?",\n'
            '    "options": ["Option A", "Option B", "Option C", "Option D"],\n'
            '    "correct_answer": "Option A",\n'
            '    "explanation": "Concise pedagogical explanation."\n'
            "  },\n"
            "  {\n"
            '    "question_type": "short_answer",\n'
            f'    "difficulty": "{target_difficulty}",\n'
            '    "prompt": "Specific concept question?",\n'
            '    "options": null,\n'
            '    "correct_answer": "Expected exact phrase or concept",\n'
            '    "explanation": "Explanation."\n'
            "  },\n"
            "  {\n"
            '    "question_type": "numerical",\n'
            f'    "difficulty": "{target_difficulty}",\n'
            '    "prompt": "Calculation question?",\n'
            '    "options": null,\n'
            '    "correct_answer": "42",\n'
            '    "explanation": "Derivation."\n'
            "  }\n"
            "]\n\n"
            f"Course Materials Context:\n{context_text}"
        )

        model = self._model
        if model is None:
            if not self.api_key:
                raise RuntimeError("GEMINI_API_KEY is not configured and no model was provided")
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            self._model = model

        response = model.generate_content(prompt)
        raw_text = (
            response.text
            if hasattr(response, "text")
            else getattr(response, "content", str(response))
        )

        cleaned_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text.strip())

        try:
            parsed = json.loads(cleaned_text)
            if not isinstance(parsed, list):
                parsed = [parsed]
        except Exception:
            match = re.search(r"\[\s*\{.*\}\s*\]", cleaned_text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
            else:
                parsed = []

        valid_questions = self.validator.validate_batch(parsed, context_text=context_text)
        default_unit_id = chunks[0].get("content_unit_id") if chunks else None
        for q in valid_questions:
            q["content_unit_id"] = default_unit_id
        return valid_questions

    def create_adaptive_assessment(
        self,
        student_id: int,
        topic_id: int,
        assessment_type: str = "adaptive_quiz",
        count: int = 3,
        target_difficulty: str | None = None,
    ) -> dict[str, Any]:
        conn = self._get_connection()
        try:
            if not target_difficulty:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT mastery_score FROM learner_mastery WHERE student_id = %s AND topic_id = %s;",
                        (student_id, topic_id),
                    )
                    row = cur.fetchone()
                    if row:
                        m_score = float((row if isinstance(row, dict) else dict(row))["mastery_score"])
                        target_difficulty = "hard" if m_score >= 0.75 else "easy" if m_score < 0.4 else "medium"
                    else:
                        target_difficulty = "medium"
        finally:
            conn.close()

        topic_title, chunks = self.get_topic_chunks(topic_id)
        if not chunks:
            raise ValueError(f"No course content units found for topic {topic_id}")

        questions = self.generate_questions(
            topic_title=topic_title,
            chunks=chunks,
            count=count,
            target_difficulty=target_difficulty or "medium",
        )

        if not questions:
            raise RuntimeError(f"Failed to generate valid assessment questions for topic '{topic_title}'")

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO assessments (student_id, assessment_type, completed)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (student_id, assessment_type, False),
                )
                assessment_id = cur.fetchone()[0]

                persisted_questions: list[dict[str, Any]] = []
                for q in questions:
                    options_json = json.dumps(q["options"]) if q.get("options") else None
                    cur.execute(
                        """
                        INSERT INTO questions
                            (topic_id, content_unit_id, question_type, difficulty, prompt, options, correct_answer, explanation)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                        RETURNING id;
                        """,
                        (
                            topic_id,
                            q.get("content_unit_id"),
                            q["question_type"],
                            q["difficulty"],
                            q["prompt"],
                            options_json,
                            q["correct_answer"],
                            q.get("explanation"),
                        ),
                    )
                    question_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        INSERT INTO assessment_questions (assessment_id, question_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING;
                        """,
                        (assessment_id, question_id),
                    )
                    persisted_questions.append({**q, "id": question_id})

                if hasattr(conn, "commit"):
                    conn.commit()

                return {
                    "assessment_id": assessment_id,
                    "student_id": student_id,
                    "topic_id": topic_id,
                    "topic_title": topic_title,
                    "assessment_type": assessment_type,
                    "questions": persisted_questions,
                }
        finally:
            conn.close()
