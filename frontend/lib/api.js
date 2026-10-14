const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = options.body instanceof FormData ? (options.headers || {}) : {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return response.json();
}

export function getHealth() {
  return request("/health");
}

export function askTutor(query, courseId = "1", topK = 5) {
  return request("/tutor/ask", {
    method: "POST",
    body: JSON.stringify({
      query,
      course_id: String(courseId),
      top_k: topK,
    }),
  });
}

export function getLearnerMastery(studentId = 1, courseId) {
  const query = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return request(`/learner/mastery/${studentId}${query}`);
}

export function getRecommendations(studentId = 1, courseId = 1, targetTopicId) {
  const query = targetTopicId ? `?target_topic_id=${encodeURIComponent(targetTopicId)}` : "";
  return request(`/learner/recommendations/${studentId}/${courseId}${query}`);
}

export function generateAssessment(studentId = 1, topicId = 1, count = 3, targetDifficulty) {
  return request("/assessment/generate", {
    method: "POST",
    body: JSON.stringify({
      student_id: Number(studentId),
      topic_id: Number(topicId),
      count: Number(count),
      target_difficulty: targetDifficulty || null,
    }),
  });
}

export function submitAssessmentAnswer(studentId = 1, assessmentId, questionId, submittedAnswer) {
  return request("/assessment/submit", {
    method: "POST",
    body: JSON.stringify({
      student_id: Number(studentId),
      assessment_id: Number(assessmentId),
      question_id: Number(questionId),
      submitted_answer: String(submittedAnswer),
    }),
  });
}

export function updateTopicMastery(studentId = 1, topicId = 1, isCorrect = true, difficulty = "medium") {
  return request("/learner/mastery/update", {
    method: "POST",
    body: JSON.stringify({
      student_id: Number(studentId),
      topic_id: Number(topicId),
      is_correct: Boolean(isCorrect),
      difficulty,
    }),
  });
}

export function uploadMaterial(courseId = "1", file, topicId) {
  const formData = new FormData();
  formData.append("file", file);
  if (topicId) {
    formData.append("topic_id", String(topicId));
  }
  return request(`/courses/${courseId}/materials`, {
    method: "POST",
    body: formData,
  });
}

export function createCourse(title, subject, description) {
  return request("/courses", {
    method: "POST",
    body: JSON.stringify({ title, subject, description }),
  });
}

export function runDiagnostic(studentId = 1, courseId = 1) {
  return request("/learner/diagnostic", {
    method: "POST",
    body: JSON.stringify({ student_id: Number(studentId), course_id: Number(courseId) }),
  });
}

export function getBenchmark() {
  return request("/evaluation/benchmark");
}
