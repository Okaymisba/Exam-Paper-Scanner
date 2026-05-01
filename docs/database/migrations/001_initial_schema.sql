-- =============================================================================
-- Migration: 001_initial_schema
-- Description: Creates the initial schema for the OBE Exam Marks Extractor.
--
-- Tables created:
--   1. exams          - exam session configuration
--   2. questions      - per-exam question definitions
--   3. students       - student roll numbers (shared across exams)
--   4. exam_results   - links students to exams
--   5. mark_entries   - individual question marks per student per exam
--
-- RLS policies use the anon role so the publishable key can read and write.
-- This is appropriate for an internal tool without end-user authentication.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. exams
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS exams (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255)  NOT NULL,
    pass_threshold  NUMERIC(5,2)  NOT NULL
                        CHECK (pass_threshold >= 1 AND pass_threshold <= 100),
    roll_prefix     VARCHAR(20)   NOT NULL,
    starting_roll   INTEGER       NOT NULL CHECK (starting_roll > 0),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

ALTER TABLE exams ENABLE ROW LEVEL SECURITY;

CREATE POLICY exams_anon_all
    ON exams
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);


-- -----------------------------------------------------------------------------
-- 2. questions
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS questions (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id         UUID          NOT NULL
                        REFERENCES exams(id) ON DELETE CASCADE,
    question_number INTEGER       NOT NULL CHECK (question_number > 0),
    clo_number      INTEGER       NOT NULL CHECK (clo_number > 0),
    max_marks       NUMERIC(6,2)  NOT NULL CHECK (max_marks > 0),
    UNIQUE (exam_id, question_number)
);

ALTER TABLE questions ENABLE ROW LEVEL SECURITY;

CREATE POLICY questions_anon_all
    ON questions
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_questions_exam_id ON questions (exam_id);


-- -----------------------------------------------------------------------------
-- 3. students
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS students (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    roll_no     VARCHAR(50)   NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

ALTER TABLE students ENABLE ROW LEVEL SECURITY;

CREATE POLICY students_anon_all
    ON students
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);


-- -----------------------------------------------------------------------------
-- 4. exam_results
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS exam_results (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id     UUID          NOT NULL
                    REFERENCES exams(id) ON DELETE CASCADE,
    student_id  UUID          NOT NULL
                    REFERENCES students(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (exam_id, student_id)
);

ALTER TABLE exam_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY exam_results_anon_all
    ON exam_results
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_exam_results_exam_id    ON exam_results (exam_id);
CREATE INDEX IF NOT EXISTS idx_exam_results_student_id ON exam_results (student_id);


-- -----------------------------------------------------------------------------
-- 5. mark_entries
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mark_entries (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id       UUID          NOT NULL
                        REFERENCES exam_results(id) ON DELETE CASCADE,
    question_id     UUID          NOT NULL
                        REFERENCES questions(id) ON DELETE CASCADE,
    obtained_marks  NUMERIC(6,2)  NOT NULL DEFAULT 0
                        CHECK (obtained_marks >= 0),
    ocr_confidence  NUMERIC(5,2)  NULL,
    UNIQUE (result_id, question_id)
);

ALTER TABLE mark_entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY mark_entries_anon_all
    ON mark_entries
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_mark_entries_result_id   ON mark_entries (result_id);
CREATE INDEX IF NOT EXISTS idx_mark_entries_question_id ON mark_entries (question_id);
