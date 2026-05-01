# Database Schema Reference

## Technology

- **Database:** PostgreSQL via Supabase
- **Connection:** Supabase Python client (supabase-py)
- **Key type:** Publishable (anon) key with permissive RLS policies

---

## Tables

### exams

Stores one record per exam session configured by the teacher.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | UUID | No | gen_random_uuid() | Primary key |
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

**Unique constraint:** (exam_id, question_number) - a question number cannot be duplicated within the same exam.

---

### students

Stores one record per unique student roll number. Students are shared across exams.

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

**Unique constraint:** (exam_id, student_id) - a student can only have one result record per exam.

---

### mark_entries

Stores the marks obtained by a student for each question in an exam. This is the most granular table in the schema.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | UUID | No | gen_random_uuid() | Primary key |
| result_id | UUID | No | | FK to exam_results(id), cascades on delete |
| question_id | UUID | No | | FK to questions(id), cascades on delete |
| obtained_marks | NUMERIC(6,2) | No | 0 | Marks scored (0 or more) |
| ocr_confidence | NUMERIC(5,2) | Yes | NULL | OCR confidence percentage; NULL if manually entered |

**Unique constraint:** (result_id, question_id) - one mark entry per question per student per exam.

---

## Relationships

```
exams
  |-- questions         (exam_id)
  |-- exam_results      (exam_id)
        |-- mark_entries   (result_id)
              |-- questions  (question_id)

students
  |-- exam_results      (student_id)
```

Cascade deletes are enabled on all foreign keys. Deleting an exam removes all its questions, results, and marks.

---

## Useful Queries

### Get all results for an exam with marks per CLO

```sql
SELECT
    s.roll_no,
    q.clo_number,
    SUM(me.obtained_marks) AS clo_total,
    SUM(q.max_marks) AS clo_max
FROM exam_results er
JOIN students s ON s.id = er.student_id
JOIN mark_entries me ON me.result_id = er.id
JOIN questions q ON q.id = me.question_id
WHERE er.exam_id = '<exam_uuid>'
GROUP BY s.roll_no, q.clo_number
ORDER BY s.roll_no, q.clo_number;
```

### Get pass/fail summary for an exam

```sql
SELECT
    s.roll_no,
    SUM(me.obtained_marks) AS total_obtained,
    SUM(q.max_marks) AS total_max,
    ROUND(SUM(me.obtained_marks) / SUM(q.max_marks) * 100, 2) AS percentage,
    CASE
        WHEN ROUND(SUM(me.obtained_marks) / SUM(q.max_marks) * 100, 2) >= e.pass_threshold
        THEN 'Pass'
        ELSE 'Fail'
    END AS result
FROM exam_results er
JOIN exams e ON e.id = er.exam_id
JOIN students s ON s.id = er.student_id
JOIN mark_entries me ON me.result_id = er.id
JOIN questions q ON q.id = me.question_id
WHERE er.exam_id = '<exam_uuid>'
GROUP BY s.roll_no, e.pass_threshold
ORDER BY s.roll_no;
```

---

## Migration File

See `migrations/001_initial_schema.sql` for the full DDL to create all tables, indexes, constraints, and RLS policies.
