"""
Supabase database layer for OBE Exam Marks Extractor.

Provides functions to persist exam configuration, questions,
student records, and mark entries to Supabase.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_SUPABASE_URL: str = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
_SUPABASE_KEY: str = os.environ["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"]


def _client() -> Client:
    return create_client(_SUPABASE_URL, _SUPABASE_KEY)


def create_exam(exam_name: str, pass_threshold: float,
                roll_prefix: str, starting_roll: int,
                questions: list[dict]) -> str:
    """
    Insert one exam record and its questions.

    Args:
        exam_name:      Display name of the exam.
        pass_threshold: Passing percentage (e.g., 50.0).
        roll_prefix:    Department code (e.g., "SE").
        starting_roll:  Starting roll number integer (e.g., 24001).
        questions:      List of dicts with keys: no, clo, maxMarks.

    Returns:
        The UUID of the created exam record.
    """
    db = _client()

    exam_row = db.table("exams").insert({
        "name":           exam_name,
        "pass_threshold": pass_threshold,
        "roll_prefix":    roll_prefix,
        "starting_roll":  starting_roll,
    }).execute()

    exam_id: str = exam_row.data[0]["id"]

    question_rows = [
        {
            "exam_id":         exam_id,
            "question_number": int(q["no"]),
            "clo_number":      int(q["clo"]),
            "max_marks":       float(q["maxMarks"]),
        }
        for q in questions
    ]

    db.table("questions").insert(question_rows).execute()

    return exam_id


def save_student_result(exam_id: str, student_roll_no: str,
                        marks: list[dict],
                        question_id_map: dict[int, str]) -> str:
    """
    Upsert a student record and save their marks for one exam.

    Args:
        exam_id:         UUID of the exam.
        student_roll_no: Full roll number string (e.g., "SE-24001").
        marks:           List of dicts with keys: questionNo, obtained, confidence.
        question_id_map: Mapping of question_number -> question UUID.

    Returns:
        The UUID of the exam_results record.
    """
    db = _client()

    existing = (
        db.table("students")
        .select("id")
        .eq("roll_no", student_roll_no)
        .execute()
    )

    if existing.data:
        student_id: str = existing.data[0]["id"]
    else:
        student_id = (
            db.table("students")
            .insert({"roll_no": student_roll_no})
            .execute()
            .data[0]["id"]
        )

    result_row = db.table("exam_results").insert({
        "exam_id":    exam_id,
        "student_id": student_id,
    }).execute()

    result_id: str = result_row.data[0]["id"]

    mark_rows = []
    for m in marks:
        q_no = int(m["questionNo"])
        q_id = question_id_map.get(q_no)
        if q_id is None:
            continue
        mark_rows.append({
            "result_id":      result_id,
            "question_id":    q_id,
            "obtained_marks": float(m.get("obtained", 0)),
            "ocr_confidence": m.get("confidence") or None,
        })

    if mark_rows:
        db.table("mark_entries").insert(mark_rows).execute()

    return result_id


def get_question_id_map(exam_id: str) -> dict[int, str]:
    """
    Return a dict mapping question_number -> question UUID for an exam.

    Args:
        exam_id: UUID of the exam.

    Returns:
        Dict like {1: "uuid-...", 2: "uuid-...", ...}
    """
    db = _client()
    rows = (
        db.table("questions")
        .select("id, question_number")
        .eq("exam_id", exam_id)
        .execute()
        .data
    )
    return {row["question_number"]: row["id"] for row in rows}
