CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    parent_id INT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    order_index INT DEFAULT 0 CHECK (order_index >= 0),
    CONSTRAINT uq_topics_id_course UNIQUE (id, course_id),
    CONSTRAINT fk_topics_parent_same_course FOREIGN KEY (parent_id, course_id) REFERENCES topics(id, course_id) ON DELETE CASCADE,
    CHECK (id <> parent_id)
);

CREATE TABLE topic_prerequisites (
    topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    prerequisite_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (topic_id, prerequisite_id),
    CHECK (topic_id <> prerequisite_id)
);

CREATE TABLE content_units (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(255) NOT NULL,
    file_id VARCHAR(255) NOT NULL,
    course_id VARCHAR(255) NOT NULL,
    filename VARCHAR(512) NOT NULL,
    topic_id INT REFERENCES topics(id) ON DELETE SET NULL,
    source_type VARCHAR(50) NOT NULL,
    source_uri VARCHAR(512) NOT NULL,
    page_number INT CHECK (page_number IS NULL OR page_number >= 1),
    slide_number INT CHECK (slide_number IS NULL OR slide_number >= 1),
    video_timestamp FLOAT CHECK (video_timestamp IS NULL OR video_timestamp >= 0),
    content_text TEXT NOT NULL,
    content_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    content_unit_id INT NOT NULL REFERENCES content_units(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1536),
    content_hash VARCHAR(64),
    embedding_model VARCHAR(255),
    metadata JSONB,
    UNIQUE (content_unit_id, chunk_index)
);

ALTER TABLE content_units
    ADD CONSTRAINT uq_content_units_course_file_source UNIQUE (course_id, file_id, source_id);

CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    content_unit_id INT REFERENCES content_units(id) ON DELETE SET NULL,
    question_type VARCHAR(50) NOT NULL CHECK (question_type IN ('MCQ', 'short_answer', 'numerical')),
    difficulty VARCHAR(20) NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    prompt TEXT NOT NULL,
    options JSONB,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_mcq_options CHECK (question_type <> 'MCQ' OR (options IS NOT NULL AND jsonb_typeof(options) = 'array'))
);

CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE learner_mastery (
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    mastery_score NUMERIC(5,4) NOT NULL DEFAULT 0.0 CHECK (mastery_score BETWEEN 0.0 AND 1.0),
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0.0 CHECK (confidence BETWEEN 0.0 AND 1.0),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_id, topic_id)
);

CREATE TABLE assessments (
    id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    assessment_type VARCHAR(50) NOT NULL,
    score NUMERIC(5,2) CHECK (score >= 0.0 AND score <= 100.0),
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_assessment_student UNIQUE (id, student_id)
);

CREATE TABLE assessment_questions (
    assessment_id INT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_id INT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    PRIMARY KEY (assessment_id, question_id),
    CONSTRAINT uq_assessment_question_pair UNIQUE (assessment_id, question_id)
);

CREATE TABLE student_answers (
    id SERIAL PRIMARY KEY,
    assessment_id INT NOT NULL,
    question_id INT NOT NULL,
    student_id INT NOT NULL,
    submitted_answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    feedback TEXT,
    misconception_detected TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_assessment_question UNIQUE (student_id, assessment_id, question_id),
    CONSTRAINT fk_answer_assessment_student FOREIGN KEY (assessment_id, student_id) REFERENCES assessments(id, student_id) ON DELETE CASCADE,
    CONSTRAINT fk_answer_assessment_question FOREIGN KEY (assessment_id, question_id) REFERENCES assessment_questions(assessment_id, question_id) ON DELETE CASCADE
);

CREATE TABLE evaluation_logs (
    id SERIAL PRIMARY KEY,
    pipeline_stage VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metadata JSONB,
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_topics_course_id ON topics(course_id);
CREATE INDEX idx_topics_parent_id ON topics(parent_id);
CREATE INDEX idx_content_units_topic_id ON content_units(topic_id);
CREATE INDEX idx_content_units_course_file ON content_units(course_id, file_id);
CREATE INDEX idx_chunks_content_unit_id ON chunks(content_unit_id);
CREATE INDEX idx_chunks_embedding_cosine ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_questions_topic_id ON questions(topic_id);
CREATE INDEX idx_learner_mastery_student_id ON learner_mastery(student_id);
CREATE INDEX idx_topic_prerequisites_prerequisite_id ON topic_prerequisites(prerequisite_id);
CREATE INDEX idx_assessments_student_id ON assessments(student_id);
CREATE INDEX idx_assessment_questions_question_id ON assessment_questions(question_id);
CREATE INDEX idx_student_answers_question_id ON student_answers(question_id);
CREATE INDEX idx_student_answers_student_id ON student_answers(student_id);
CREATE INDEX idx_evaluation_logs_metric ON evaluation_logs(metric_name);