# Database Schema Reference

## Technology

- **Database:** PostgreSQL via Supabase
- **Connection:** Supabase Python client (supabase-py)
- **Auth:** Supabase Auth (email and password)
- **Key type:** Publishable (anon) key; RLS enforces data isolation per teacher

---

## Tables

### teacher_profiles

Stores one profile record per registered teacher. Each row is linked to a Supabase Auth user. Teachers go through an admin-approval workflow before they can access the application.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | UUID | No | | Primary key, FK to auth.users(id) |
| full_name | VARCHAR(255) | No | | Teacher's display name |
| email | VARCHAR(255) | No | | Login email address, unique |
| department | VARCHAR(100) | Yes | NULL | Academic department |
| role | VARCHAR(20) | No | 'teacher' | 'teacher' or 'admin' |
| status | VARCHAR(20) | No | 'pending' | 'pending', 'approved', or 'rejected' |
| requested_at | TIMESTAMPTZ | No | NOW() | When the signup request was submitted |
| reviewed_at | TIMESTAMPTZ | Yes | NULL | When an admin acted on the request |
| reviewed_by | UUID | Yes | NULL | FK to auth.users(id) of the reviewing admin |

---

### exams

Stores one record per exam session configured by a teacher. Each exam is owned by the teacher who created it.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | UUID | No | gen_random_uuid() | Primary key |
| teacher_id | UUID | No | | FK to auth.users(id), the owning teacher |
| name | VARCHAR(255) | No | | Exam or subject name |
| pass_threshold | NUMERIC(5,2) | No | | Minimum passing percentage (1 to 100) |
| roll_prefix | VARCHAR(20) | No | | Department code prefix (e.g., SE, CS) |
| starting_roll | INTEGER | No | | Starting roll number for the session |
| created_at | TIMESTAMPTZ | No | NOW() | Record creation timestamp |

---

### questions

Stores one record per question in an exam. Each question is linked to a CLO.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | UUID | No | gen_random_uuid() | Primary key |
| exam_id | UUID | No | | FK to exams(id), cascades on delete |
| question_number | INTEGER | No | | Question sequence number (1-based) |
| clo_number | INTEGER | No | | Course Learning Outcome number |
| max_marks | NUMERIC(6,2) | No | | Maximum marks for this question |

**Unique constraint:** (exam_id, question_number)

---

### students

Stores one record per unique student roll number. Students are shared across exams and teachers.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | UUID | No | gen_random_uuid() | Primary key |
| roll_no | VARCHAR(50) | No | | Full roll number (e.g., SE-24001), unique |
| created_at | TIMESTAMPTZ | No | NOW() | Record creation timestamp |

---

### exam_results

Junction table linking a student to a specific exam. One record per student-exam pair.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | UUID | No | gen_random_uuid() | Primary key |
| exam_id | UUID | No | | FK to exams(id), cascades on delete |
| student_id | UUID | No | | FK to students(id), cascades on delete |
| created_at | TIMESTAMPTZ | No | NOW() | Record creation timestamp |

**Unique constraint:** (exam_id, student_id)

---

### mark_entries

Stores the marks obtained by a student for each question in an exam.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | UUID | No | gen_random_uuid() | Primary key |
| result_id | UUID | No | | FK to exam_results(id), cascades on delete |
| question_id | UUID | No | | FK to questions(id), cascades on delete |
| obtained_marks | NUMERIC(6,2) | No | 0 | Marks scored (0 or more) |
| ocr_confidence | NUMERIC(5,2) | Yes | NULL | OCR confidence percentage; NULL if manually entered |

**Unique constraint:** (result_id, question_id)

---

## Relationships

```
auth.users (1) ---- (1)    teacher_profiles
auth.users (1) ---- (many) exams              (via teacher_id)

exams
  |-- questions          (exam_id)
  |-- exam_results       (exam_id)
        |-- mark_entries    (result_id)

students
  |-- exam_results       (student_id)

questions
  |-- mark_entries       (question_id)
```

Cascade deletes are enabled. Deleting an exam removes its questions, results, and marks.

---

## Row-Level Security Summary

| Table | Policy | Who Can Access |
|---|---|---|
| teacher_profiles | INSERT | Any role (anon or authenticated) |
| teacher_profiles | SELECT | Own profile, or all if admin |
| teacher_profiles | UPDATE | Admin only |
| exams | ALL | Authenticated teachers (own exams only, via teacher_id) |
| questions | ALL | Authenticated teachers (own exams only) |
| students | ALL | Any authenticated user (roll numbers are not sensitive) |
| exam_results | ALL | Authenticated teachers (own exams only) |
| mark_entries | ALL | Authenticated teachers (own exams only) |

The `is_admin()` helper function (SECURITY DEFINER) reads from `teacher_profiles` to check role without triggering RLS recursion.

---

## Auth Workflow

```
1. Teacher submits signup request
      -> Supabase Auth creates auth.users record
      -> Python server inserts teacher_profiles (status = 'pending')

2. Admin logs in -> views pending requests -> approves or rejects
      -> teacher_profiles updated (status = 'approved' or 'rejected')

3. Approved teacher logs in
      -> Supabase Auth returns JWT
      -> Python server validates JWT, checks status = 'approved'
      -> Teacher can create exams (teacher_id set to auth.uid())
      -> RLS ensures teacher only sees own exams
```

---

## Useful Queries

### List all pending signup requests (admin)

```sql
SELECT id, full_name, email, department, requested_at
FROM   teacher_profiles
WHERE  status = 'pending'
ORDER  BY requested_at;
```

### Get a teacher's exam history with student count

```sql
SELECT
    e.id,
    e.name,
    e.created_at,
    COUNT(er.id) AS student_count
FROM   exams e
LEFT   JOIN exam_results er ON er.exam_id = e.id
WHERE  e.teacher_id = '<teacher_uuid>'
GROUP  BY e.id, e.name, e.created_at
ORDER  BY e.created_at DESC;
```

### Get all results for an exam with marks per CLO

```sql
SELECT
    s.roll_no,
    q.clo_number,
    SUM(me.obtained_marks) AS clo_total,
    SUM(q.max_marks)       AS clo_max
FROM   exam_results er
JOIN   students s    ON s.id    = er.student_id
JOIN   mark_entries me ON me.result_id = er.id
JOIN   questions q   ON q.id   = me.question_id
WHERE  er.exam_id = '<exam_uuid>'
GROUP  BY s.roll_no, q.clo_number
ORDER  BY s.roll_no, q.clo_number;
```

### Get pass/fail summary for an exam

```sql
SELECT
    s.roll_no,
    SUM(me.obtained_marks) AS total_obtained,
    SUM(q.max_marks)       AS total_max,
    ROUND(SUM(me.obtained_marks) / SUM(q.max_marks) * 100, 2) AS percentage,
    CASE
        WHEN ROUND(SUM(me.obtained_marks) / SUM(q.max_marks) * 100, 2) >= e.pass_threshold
        THEN 'Pass' ELSE 'Fail'
    END AS result
FROM   exam_results er
JOIN   exams e         ON e.id    = er.exam_id
JOIN   students s      ON s.id    = er.student_id
JOIN   mark_entries me ON me.result_id = er.id
JOIN   questions q     ON q.id   = me.question_id
WHERE  er.exam_id = '<exam_uuid>'
GROUP  BY s.roll_no, e.pass_threshold
ORDER  BY s.roll_no;
```

---

## Migration Files

| File | Description |
|---|---|
| `migrations/001_initial_schema.sql` | Creates core tables (exams, questions, students, exam_results, mark_entries) |
| `migrations/002_auth_and_accounts.sql` | Adds teacher_profiles, teacher_id on exams, auth RLS policies |
