# Database Normalization Analysis

## Overview

This document walks through the normalization of the OBE Exam Marks Extractor data model from an un-normalized flat structure to Third Normal Form (3NF). The purpose is to eliminate data redundancy, prevent update anomalies, and produce a clean relational schema suitable for a production database.

---

## Source Data Model (Un-normalized Form)

When a teacher processes an exam session, the application works with the following attributes:

| Attribute | Description |
|---|---|
| exam_name | Name of the exam or subject (e.g., "SE-209 CALD Mid Term") |
| pass_threshold | Minimum passing percentage (e.g., 50) |
| roll_prefix | Department code prefix (e.g., SE, CS, EE) |
| starting_roll | First roll number in the exam session (e.g., 24001) |
| question_number | Sequence number of the question (e.g., 1, 2, 3) |
| clo_number | Course Learning Outcome linked to this question (e.g., 1, 2) |
| max_marks | Maximum marks allocated to the question (e.g., 10.0) |
| student_roll_no | Full roll number of the student (e.g., SE-24001) |
| obtained_marks | Marks scored by the student on a question (e.g., 7.5) |
| ocr_confidence | OCR extraction confidence percentage (e.g., 85.0) |
| recorded_at | Timestamp when the data was saved |

In its un-normalized state, a single exam record is a nested structure with repeating groups:

```
Exam_Session {
    exam_name,
    pass_threshold,
    roll_prefix,
    starting_roll,

    Questions (repeating group): [
        { question_number, clo_number, max_marks },
        { question_number, clo_number, max_marks },
        ...
    ],

    Students (repeating group): [
        {
            student_roll_no,
            Marks (nested repeating group): [
                { question_number, obtained_marks, ocr_confidence },
                { question_number, obtained_marks, ocr_confidence },
                ...
            ]
        },
        ...
    ]
}
```

**Problems with this structure:**

- Nested repeating groups cannot be directly stored in a relational table
- Exam-level data (name, pass_threshold, roll_prefix) is duplicated for every student and every question row
- Question metadata (clo_number, max_marks) is duplicated for every student who answers that question
- Inserting, updating, or deleting any record risks inconsistency across duplicated data

---

## First Normal Form (1NF)

**Rules applied:**
- Eliminate all repeating groups by creating one row per atomic unit of data
- Ensure every column holds a single (atomic) value
- Define a primary key that uniquely identifies each row

We flatten the nested structure into a single table. Each row represents one student's marks for one question in one exam.

**Table: ExamData**

| Column | Notes |
|---|---|
| exam_name | Part of composite PK |
| student_roll_no | Part of composite PK |
| question_number | Part of composite PK |
| pass_threshold | Exam-level attribute |
| roll_prefix | Exam-level attribute |
| starting_roll | Exam-level attribute |
| clo_number | Question-level attribute |
| max_marks | Question-level attribute |
| obtained_marks | Mark-level attribute |
| ocr_confidence | Mark-level attribute |
| recorded_at | Mark-level attribute |

**Primary Key:** (exam_name, student_roll_no, question_number)

The table is now in 1NF: every cell contains a single value, there are no repeating groups, and every row has a unique composite primary key.

**Remaining problems:**

- exam_name appearing in every row means pass_threshold, roll_prefix, and starting_roll are repeated for every student-question combination
- question_number appearing in every row means clo_number and max_marks are repeated for every student who answers that question
- These are partial dependencies on the composite key, which violates 2NF

---

## Second Normal Form (2NF)

**Rules applied:**
- Must satisfy 1NF
- Every non-key attribute must depend on the WHOLE primary key, not just a portion of it

The composite primary key is **(exam_name, student_roll_no, question_number)**.

**Partial dependencies identified:**

| Attribute | Depends On | Dependency Type |
|---|---|---|
| pass_threshold | exam_name only | Partial - violates 2NF |
| roll_prefix | exam_name only | Partial - violates 2NF |
| starting_roll | exam_name only | Partial - violates 2NF |
| clo_number | (exam_name, question_number) only | Partial - violates 2NF |
| max_marks | (exam_name, question_number) only | Partial - violates 2NF |
| obtained_marks | (exam_name, student_roll_no, question_number) | Full dependency - OK |
| ocr_confidence | (exam_name, student_roll_no, question_number) | Full dependency - OK |
| recorded_at | (exam_name, student_roll_no, question_number) | Full dependency - OK |

**Resolution:** Extract each partial dependency into its own table.

---

### Tables After 2NF

**Table: Exams**

Stores exam-level information. All attributes depend fully on exam_name.

| Column | Key Role |
|---|---|
| exam_name | Primary Key |
| pass_threshold | |
| roll_prefix | |
| starting_roll | |

**Table: Questions**

Stores question metadata per exam. Both clo_number and max_marks depend on the full key (exam_name, question_number).

| Column | Key Role |
|---|---|
| exam_name | Primary Key (part 1) + FK to Exams |
| question_number | Primary Key (part 2) |
| clo_number | |
| max_marks | |

**Table: StudentMarks**

Stores the actual marks obtained. obtained_marks and ocr_confidence depend on the full composite key.

| Column | Key Role |
|---|---|
| exam_name | Primary Key (part 1) + FK to Exams |
| student_roll_no | Primary Key (part 2) |
| question_number | Primary Key (part 3) + FK to Questions |
| obtained_marks | |
| ocr_confidence | |
| recorded_at | |

The redundancy in exam-level and question-level data has been eliminated. Each fact is stored in exactly one place.

---

## Third Normal Form (3NF)

**Rules applied:**
- Must satisfy 2NF
- No non-key attribute should depend on another non-key attribute (no transitive dependencies)

**Checking each 2NF table for transitive dependencies:**

**Exams:** pass_threshold, roll_prefix, and starting_roll all depend directly on exam_name. None of them depend on each other. No transitive dependencies.

**Questions:** clo_number and max_marks both depend directly on (exam_name, question_number). Neither depends on the other. No transitive dependencies.

**StudentMarks:** obtained_marks, ocr_confidence, and recorded_at all depend directly on the full composite key. No transitive dependencies.

The 2NF tables already satisfy 3NF.

---

## Final Refinements Before Implementation

Two practical improvements are applied before creating the database tables:

**1. Surrogate primary keys**

Using exam_name as a primary key is fragile. Exam names can have typos, change over time, or collide across departments. Natural string keys also perform worse as foreign key references. Each table receives a UUID primary key column (id), and the natural keys become regular columns with unique constraints where needed.

**2. Student entity extraction**

In the 2NF design, student_roll_no is embedded inside StudentMarks. A student (identified by roll_no) is a real-world entity that can appear in multiple exams. Extracting students into their own table with a surrogate key:
- Avoids repeating the roll_no string in every mark row
- Allows a future student profile to be added without schema changes
- Makes the relationship between students and exams explicit via a junction table

An intermediate exam_results table links students to exams (capturing which student sat which exam), and mark_entries stores the individual question marks linked to that result.

---

## Final 3NF Schema

### exams

| Column | Type | Constraints |
|---|---|---|
| id | UUID | Primary Key, default gen_random_uuid() |
| name | VARCHAR(255) | NOT NULL |
| pass_threshold | NUMERIC(5,2) | NOT NULL, between 1 and 100 |
| roll_prefix | VARCHAR(20) | NOT NULL |
| starting_roll | INTEGER | NOT NULL, > 0 |
| created_at | TIMESTAMPTZ | Default NOW() |

### questions

| Column | Type | Constraints |
|---|---|---|
| id | UUID | Primary Key |
| exam_id | UUID | NOT NULL, FK to exams(id) |
| question_number | INTEGER | NOT NULL, > 0 |
| clo_number | INTEGER | NOT NULL, > 0 |
| max_marks | NUMERIC(6,2) | NOT NULL, > 0 |
| UNIQUE | (exam_id, question_number) | |

### students

| Column | Type | Constraints |
|---|---|---|
| id | UUID | Primary Key |
| roll_no | VARCHAR(50) | NOT NULL, UNIQUE |
| created_at | TIMESTAMPTZ | Default NOW() |

### exam_results

| Column | Type | Constraints |
|---|---|---|
| id | UUID | Primary Key |
| exam_id | UUID | NOT NULL, FK to exams(id) |
| student_id | UUID | NOT NULL, FK to students(id) |
| created_at | TIMESTAMPTZ | Default NOW() |
| UNIQUE | (exam_id, student_id) | |

### mark_entries

| Column | Type | Constraints |
|---|---|---|
| id | UUID | Primary Key |
| result_id | UUID | NOT NULL, FK to exam_results(id) |
| question_id | UUID | NOT NULL, FK to questions(id) |
| obtained_marks | NUMERIC(6,2) | NOT NULL, >= 0 |
| ocr_confidence | NUMERIC(5,2) | Nullable (NULL when manually entered) |
| UNIQUE | (result_id, question_id) | |

---

## Entity Relationship Summary (Phase 1)

```
exams (1) ---- (many) questions
exams (1) ---- (many) exam_results
students (1) -- (many) exam_results
exam_results (1) ---- (many) mark_entries
questions (1) ------- (many) mark_entries
```

Every non-key attribute in every table depends on:
- The primary key
- The whole primary key
- Nothing but the primary key

This satisfies the definition of Third Normal Form.

---

## Phase 2 Normalization: Teacher Accounts and Authentication

With the addition of teacher account management, a new entity enters the data model. This section applies the same normalization process to the authentication-related data.

### New Source Attributes

When a teacher registers for an account, the following attributes are collected:

| Attribute | Description |
|---|---|
| user_id | Identity token issued by Supabase Auth (UUID) |
| full_name | Teacher's display name |
| email | Email address used for login |
| department | Academic department (optional) |
| role | System role: teacher or admin |
| status | Approval state: pending, approved, or rejected |
| requested_at | Timestamp of the signup request |
| reviewed_at | Timestamp when an admin acted on the request |
| reviewed_by | Admin user who reviewed the request |

Additionally, the existing `exams` table gains:

| Attribute | Description |
|---|---|
| teacher_id | The user_id of the teacher who created this exam |

### Normalization of teacher_profiles

**Un-normalized consideration:**

There is no repeating group in a teacher profile. Each teacher has exactly one profile with one set of attributes. The entity is already flat by nature.

**1NF check:**

Every attribute is atomic. The `role` and `status` columns use constrained string values (not sets or arrays). A single row represents one teacher's account.

Primary Key: user_id (UUID from auth.users)

The table is in 1NF by design.

**2NF check:**

The primary key is a single column (user_id), so partial dependencies cannot exist. A composite key is not involved.

The table is in 2NF by design.

**3NF check:**

Checking for transitive dependencies among non-key attributes:

| Attribute | Depends On | Transitive Dependency? |
|---|---|---|
| full_name | user_id | No |
| email | user_id | No |
| department | user_id | No |
| role | user_id | No |
| status | user_id | No |
| requested_at | user_id | No |
| reviewed_at | user_id | No |
| reviewed_by | user_id | No |

No attribute depends on another non-key attribute. `status` changes over time but does not functionally depend on `role` or any other column. `reviewed_at` and `reviewed_by` depend on the row's primary key, not on `status` (even though they are only populated when status changes, this is a business rule, not a functional dependency).

The table is in 3NF.

**Relationship to exams:**

Adding `teacher_id` to the `exams` table introduces a foreign key reference from `exams` to `auth.users`. This does not affect the normalization of `exams` because `teacher_id` is a foreign key attribute that depends directly on the exam's primary key. All other attributes of `exams` (name, pass_threshold, roll_prefix, starting_roll) remain dependent only on `id`.

### Updated Entity Relationship Summary

```
auth.users (1) ---- (1) teacher_profiles
auth.users (1) ---- (many) exams          (via teacher_id)

exams (1) ---- (many) questions
exams (1) ---- (many) exam_results
students (1) -- (many) exam_results
exam_results (1) ---- (many) mark_entries
questions (1) ------- (many) mark_entries
```

The complete schema across both phases satisfies Third Normal Form throughout. Every non-key attribute in every table depends on the primary key, the whole primary key, and nothing but the primary key.
