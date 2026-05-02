-- =============================================================================
-- Migration: 002_auth_and_accounts
-- Description: Adds teacher account management with signup-approval workflow.
--
-- Correct execution order (PostgreSQL validates SQL-function bodies at
-- creation time, so teacher_profiles must exist before is_admin() is created,
-- and is_admin() must exist before the policies that call it are created):
--
--   1. Create teacher_profiles table
--   2. Enable RLS + add the insert-only policy (needs no helper function)
--   3. Create is_admin() helper function
--   4. Add the select / update policies that call is_admin()
--   5. Add teacher_id column to exams
--   6. Drop old anon policies from migration 001
--   7. Add new authenticated-user policies for all tables
--
-- Prerequisites: Run 001_initial_schema.sql first.
--
-- Key concept: in Supabase/PostgREST, RLS policies alone are not enough.
-- The PostgreSQL role (anon or authenticated) must also have the privilege
-- GRANTED at the table level. RLS then filters which rows are visible.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Step 1. Create teacher_profiles
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS teacher_profiles (
    id           UUID          PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name    VARCHAR(255)  NOT NULL,
    email        VARCHAR(255)  NOT NULL UNIQUE,
    department   VARCHAR(100),
    role         VARCHAR(20)   NOT NULL DEFAULT 'teacher'
                     CHECK (role IN ('teacher', 'admin')),
    status       VARCHAR(20)   NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'approved', 'rejected')),
    requested_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    reviewed_at  TIMESTAMPTZ,
    reviewed_by  UUID          REFERENCES auth.users(id)
);


-- -----------------------------------------------------------------------------
-- Step 2. Enable RLS and add the simple insert policy
--         (no reference to is_admin() here)
-- -----------------------------------------------------------------------------

ALTER TABLE teacher_profiles ENABLE ROW LEVEL SECURITY;

-- Anyone (including the anon role) can insert a profile.
-- The Python server enforces role and status values before inserting.
CREATE POLICY tp_insert ON teacher_profiles
    FOR INSERT
    WITH CHECK (true);


-- -----------------------------------------------------------------------------
-- Step 3. Create is_admin() helper
--         teacher_profiles now exists, so the SQL body can be validated.
--         SECURITY DEFINER lets the function read teacher_profiles without
--         going through RLS, which prevents infinite recursion.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT COALESCE(
        (SELECT role = 'admin'
         FROM   public.teacher_profiles
         WHERE  id = auth.uid()),
        FALSE
    );
$$;


-- -----------------------------------------------------------------------------
-- Step 4. Add the policies that call is_admin()
-- -----------------------------------------------------------------------------

-- Users can read their own profile; admins can read all profiles.
CREATE POLICY tp_select ON teacher_profiles
    FOR SELECT TO authenticated
    USING (id = auth.uid() OR public.is_admin());

-- Only admins can update profiles (approve / reject).
CREATE POLICY tp_update ON teacher_profiles
    FOR UPDATE TO authenticated
    USING    (public.is_admin())
    WITH CHECK (public.is_admin());


-- -----------------------------------------------------------------------------
-- Step 5. Add teacher_id to exams
-- -----------------------------------------------------------------------------

ALTER TABLE exams
    ADD COLUMN IF NOT EXISTS teacher_id UUID REFERENCES auth.users(id);


-- -----------------------------------------------------------------------------
-- Step 6. Drop old permissive anon policies from migration 001
-- -----------------------------------------------------------------------------

DROP POLICY IF EXISTS exams_anon_all        ON exams;
DROP POLICY IF EXISTS questions_anon_all    ON questions;
DROP POLICY IF EXISTS students_anon_all     ON students;
DROP POLICY IF EXISTS exam_results_anon_all ON exam_results;
DROP POLICY IF EXISTS mark_entries_anon_all ON mark_entries;


-- -----------------------------------------------------------------------------
-- Step 7. New authenticated-user RLS policies
-- -----------------------------------------------------------------------------

-- exams: each teacher sees and manages only their own exams
CREATE POLICY exams_own ON exams
    FOR ALL TO authenticated
    USING    (teacher_id = auth.uid())
    WITH CHECK (teacher_id = auth.uid());

-- questions: accessible when the parent exam belongs to the current user
CREATE POLICY questions_own ON questions
    FOR ALL TO authenticated
    USING (
        exam_id IN (
            SELECT id FROM exams WHERE teacher_id = auth.uid()
        )
    )
    WITH CHECK (
        exam_id IN (
            SELECT id FROM exams WHERE teacher_id = auth.uid()
        )
    );

-- students: roll numbers are not sensitive; any authenticated teacher may
-- read and create student records. Data isolation is enforced at exam_results.
CREATE POLICY students_authenticated ON students
    FOR ALL TO authenticated
    USING    (true)
    WITH CHECK (true);

-- exam_results: scoped to the owning teacher's exams
CREATE POLICY exam_results_own ON exam_results
    FOR ALL TO authenticated
    USING (
        exam_id IN (
            SELECT id FROM exams WHERE teacher_id = auth.uid()
        )
    )
    WITH CHECK (
        exam_id IN (
            SELECT id FROM exams WHERE teacher_id = auth.uid()
        )
    );

-- mark_entries: scoped through exam_results -> exams -> teacher
CREATE POLICY mark_entries_own ON mark_entries
    FOR ALL TO authenticated
    USING (
        result_id IN (
            SELECT er.id
            FROM   exam_results er
            JOIN   exams e ON e.id = er.exam_id
            WHERE  e.teacher_id = auth.uid()
        )
    )
    WITH CHECK (
        result_id IN (
            SELECT er.id
            FROM   exam_results er
            JOIN   exams e ON e.id = er.exam_id
            WHERE  e.teacher_id = auth.uid()
        )
    );


-- -----------------------------------------------------------------------------
-- Step 8. Grant table-level privileges
--         RLS controls which rows each role can touch, but the role must
--         first have the privilege at the table level or PostgREST will
--         reject the request before RLS even runs.
-- -----------------------------------------------------------------------------

-- anon role: only needs INSERT on teacher_profiles (for the signup flow,
-- where the Python server creates the profile before the user has a session).
GRANT INSERT ON public.teacher_profiles TO anon;

-- authenticated role: full access to all tables; RLS policies handle isolation.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.teacher_profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.exams            TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.questions        TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.students         TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.exam_results     TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.mark_entries     TO authenticated;
