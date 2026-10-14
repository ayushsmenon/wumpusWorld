import json
import math
import re
from typing import Any, Sequence


VALID_QUESTION_TYPES = {"MCQ", "short_answer", "numerical"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with",
    "by", "of", "from", "is", "are", "was", "were", "what", "which", "how",
    "why", "when", "where", "who", "whom", "this", "that", "these", "those",
}


class AssessmentValidator:
    def normalize_difficulty(self, difficulty: Any) -> str:
        diff_str = str(difficulty or "medium").strip().lower()
        if diff_str in VALID_DIFFICULTIES:
            return diff_str
        return "medium"

    def normalize_question_type(self, question_type: Any) -> str:
        q_type_str = str(question_type or "").strip()
        for valid in VALID_QUESTION_TYPES:
            if q_type_str.lower() == valid.lower():
                return valid
        return "MCQ"

    def parse_number(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = re.sub(r"[^\d.-]", "", str(value).strip())
        try:
            val = float(cleaned)
            return val if math.isfinite(val) else None
        except ValueError:
            return None

    def validate_grounding(self, text: str, context_text: str | None) -> bool:
        if not context_text or not context_text.strip():
            return True
        tokens = [
            w for w in re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
            if w not in STOP_WORDS
        ]
        if not tokens:
            return True
        context_lower = context_text.lower()
        matching_tokens = [w for w in tokens if w in context_lower]
        return len(matching_tokens) >= 1

    def validate_question(
        self,
        raw_question: dict[str, Any],
        context_text: str | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        if not isinstance(raw_question, dict):
            return False, "Question must be a dictionary", {}

        prompt = str(raw_question.get("prompt") or "").strip()
        if len(prompt) < 5:
            return False, "Prompt is too short or missing", {}

        q_type = self.normalize_question_type(raw_question.get("question_type"))
        difficulty = self.normalize_difficulty(raw_question.get("difficulty"))
        explanation = str(raw_question.get("explanation") or "").strip() or None

        raw_correct = raw_question.get("correct_answer")
        if raw_correct is None or not str(raw_correct).strip():
            return False, "Missing correct_answer", {}
        correct_answer = str(raw_correct).strip()

        cleaned_options = None

        if q_type == "MCQ":
            raw_options = raw_question.get("options")
            if isinstance(raw_options, str):
                try:
                    raw_options = json.loads(raw_options)
                except Exception:
                    raw_options = [opt.strip() for opt in raw_options.split(",") if opt.strip()]

            if not isinstance(raw_options, (list, tuple)) or len(raw_options) < 2:
                return False, "MCQ questions must provide at least 2 options", {}

            options = [str(opt).strip() for opt in raw_options if str(opt).strip()]
            if len(options) < 2:
                return False, "MCQ options must have at least 2 non-empty values", {}

            matched_option = None
            for opt in options:
                if opt.lower() == correct_answer.lower():
                    matched_option = opt
                    break

            if matched_option is None:
                letter_match = re.match(r"^[A-Da-d]$", correct_answer)
                digit_match = re.match(r"^\d+$", correct_answer)
                if letter_match:
                    idx = ord(correct_answer.upper()) - ord("A")
                    if 0 <= idx < len(options):
                        matched_option = options[idx]
                elif digit_match:
                    idx = int(correct_answer)
                    if 0 <= idx < len(options):
                        matched_option = options[idx]
                    elif 1 <= idx <= len(options):
                        matched_option = options[idx - 1]

            if matched_option is None:
                return False, f"Correct answer '{correct_answer}' does not match any MCQ option", {}

            correct_answer = matched_option
            cleaned_options = options

        elif q_type == "numerical":
            num = self.parse_number(correct_answer)
            if num is None:
                return False, f"Numerical question correct_answer '{correct_answer}' is not a valid number", {}
            correct_answer = str(int(num) if num.is_integer() else num)
            cleaned_options = None

        elif q_type == "short_answer":
            cleaned_options = None

        if context_text and not self.validate_grounding(prompt + " " + correct_answer, context_text):
            return False, "Question content is not grounded in the provided course context", {}

        cleaned = {
            "prompt": prompt,
            "question_type": q_type,
            "difficulty": difficulty,
            "options": cleaned_options,
            "correct_answer": correct_answer,
            "explanation": explanation,
        }
        return True, "", cleaned

    def validate_batch(
        self,
        questions: Sequence[dict[str, Any]],
        context_text: str | None = None,
    ) -> list[dict[str, Any]]:
        valid_questions: list[dict[str, Any]] = []
        for q in questions:
            is_valid, _, cleaned = self.validate_question(q, context_text=context_text)
            if is_valid:
                valid_questions.append(cleaned)
        return valid_questions

    def verify_student_answer(
        self,
        question: dict[str, Any],
        submitted_answer: str,
    ) -> tuple[bool, str]:
        sub = str(submitted_answer or "").strip()
        cor = str(question.get("correct_answer") or "").strip()
        q_type = self.normalize_question_type(question.get("question_type"))
        explanation = question.get("explanation") or ""

        if not sub:
            return False, "No answer submitted."

        if q_type == "MCQ":
            options = question.get("options") or []
            if sub.lower() == cor.lower():
                feedback = f"Correct! {explanation}".strip()
                return True, feedback

            sub_letter = re.match(r"^[A-Da-d]$", sub)
            if sub_letter and isinstance(options, list):
                idx = ord(sub.upper()) - ord("A")
                if 0 <= idx < len(options) and options[idx].lower() == cor.lower():
                    feedback = f"Correct! {explanation}".strip()
                    return True, feedback

            feedback = f"Incorrect. The correct answer is: {cor}. {explanation}".strip()
            return False, feedback

        if q_type == "numerical":
            sub_num = self.parse_number(sub)
            cor_num = self.parse_number(cor)
            if sub_num is not None and cor_num is not None:
                tolerance = max(1e-4, abs(cor_num) * 0.01)
                if abs(sub_num - cor_num) <= tolerance:
                    feedback = f"Correct! {explanation}".strip()
                    return True, feedback
            feedback = f"Incorrect. The correct numerical answer is: {cor}. {explanation}".strip()
            return False, feedback

        sub_clean = re.sub(r"[^\w\s]", "", sub.lower()).split()
        cor_clean = re.sub(r"[^\w\s]", "", cor.lower()).split()
        if sub.lower() == cor.lower() or sub_clean == cor_clean:
            feedback = f"Correct! {explanation}".strip()
            return True, feedback

        matching = set(sub_clean) & set(cor_clean)
        if len(matching) >= max(1, len(cor_clean) * 0.6):
            feedback = f"Correct! {explanation}".strip()
            return True, feedback

        feedback = f"Incorrect. The expected answer is: {cor}. {explanation}".strip()
        return False, feedback
