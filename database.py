"""
Supabase database layer for OBE Exam Marks Extractor.

Client strategy
---------------
- _anon_client()   : Uses the publishable key with no user JWT.
                     Used for auth operations (sign_up, sign_in) and
                     for inserting teacher_profiles immediately after signup
                     (before the user has a confirmed session).
- _authed_client() : Creates a fresh client and overrides the Authorization
                     header with the user's JWT so PostgREST resolves
                     auth.uid() correctly and RLS policies apply.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_URL: str        = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
_KEY: str        = os.environ["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"]
_ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "").strip().lower()


# ── Client helpers ────────────────────────────────────────────────────────────

def _anon_client() -> Client:
    return create_client(_URL, _KEY)


def _authed_client(jwt: str) -> Client:
    client = create_client(_URL, _KEY)
    client.postgrest.auth(jwt)
    return client


# ── Auth ──────────────────────────────────────────────────────────────────────

def sign_up(email: str, password: str,
            full_name: str, department: str) -> dict:
    """
    Create a Supabase Auth user and a teacher_profiles row (status=pending).

    Returns a dict with keys: success (bool), message (str), needs_confirmation (bool).
    """
    client = _anon_client()

    auth_response = client.auth.sign_up({
        "email":    email,
        "password": password,
        "options":  {"data": {"full_name": full_name, "department": department}},
    })

    user = auth_response.user
    if not user:
        return {"success": False, "message": "Signup failed. Please try again."}

    # Determine role and initial status.
    role   = "admin"    if email.strip().lower() == _ADMIN_EMAIL else "teacher"
    status = "approved" if role == "admin"                       else "pending"

    # Use the authenticated client when a session is available (email confirmation
    # disabled). Fall back to the anon client when no session is returned yet;
    # the tp_insert policy + GRANT INSERT TO anon permits this.
    session = auth_response.session
    insert_client = _authed_client(session.access_token) if session else client

    insert_client.table("teacher_profiles").insert({
        "id":         user.id,
        "full_name":  full_name,
        "email":      email,
        "department": department or None,
        "role":       role,
        "status":     status,
    }).execute()

    if role == "admin":
        return {"success": True,
                "message": "Admin account created. You can log in now.",
                "needs_confirmation": False}

    return {"success": True,
            "message": "Request submitted. You can log in after an admin approves your account.",
            "needs_confirmation": False}


def sign_in(email: str, password: str) -> dict:
    """
    Sign in with email and password.

    Returns: {
        success, access_token, refresh_token,
        profile: { id, full_name, email, department, role, status }
    }
    Raises ValueError with a user-facing message on failure.
    """
    client = _anon_client()

    try:
        session_response = client.auth.sign_in_with_password({
            "email":    email,
            "password": password,
        })
    except Exception as exc:
        msg = str(exc).lower()
        if "invalid" in msg or "credentials" in msg or "password" in msg:
            raise ValueError("Incorrect email or password.")
        if "confirm" in msg:
            raise ValueError("Please confirm your email address before logging in.")
        raise ValueError("Login failed. Please try again.")

    session = session_response.session
    if not session:
        raise ValueError("Login failed. Please try again.")

    user = session_response.user

    # Fetch profile to check status.
    authed = _authed_client(session.access_token)
    profile_rows = (
        authed.table("teacher_profiles")
        .select("id, full_name, email, department, role, status")
        .eq("id", user.id)
        .execute()
        .data
    )

    if not profile_rows:
        raise ValueError("Account profile not found. Please contact the administrator.")

    profile = profile_rows[0]

    if profile["status"] == "pending":
        raise ValueError("Your account is pending admin approval.")
    if profile["status"] == "rejected":
        raise ValueError("Your account request was not approved. Please contact the administrator.")

    return {
        "success":       True,
        "access_token":  session.access_token,
        "refresh_token": session.refresh_token,
        "profile":       profile,
    }


def get_current_user(jwt: str) -> dict:
    """
    Validate a JWT and return the teacher profile.
    Raises ValueError if the token is invalid or the account is not approved.
    """
    client = _anon_client()
    user_response = client.auth.get_user(jwt)
    user = user_response.user
    if not user:
        raise ValueError("Invalid or expired token.")

    authed = _authed_client(jwt)
    rows = (
        authed.table("teacher_profiles")
        .select("id, full_name, email, department, role, status")
        .eq("id", user.id)
        .execute()
        .data
    )

    if not rows:
        raise ValueError("Profile not found.")
    profile = rows[0]

    if profile["status"] not in ("approved",):
        raise ValueError(f"Account status: {profile['status']}")

    return profile


# ── Admin ─────────────────────────────────────────────────────────────────────

def get_pending_requests(admin_jwt: str) -> list[dict]:
    """Return all teacher profiles with status='pending'."""
    authed = _authed_client(admin_jwt)
    return (
        authed.table("teacher_profiles")
        .select("id, full_name, email, department, requested_at, status")
        .eq("status", "pending")
        .order("requested_at")
        .execute()
        .data
    )


def get_all_teachers(admin_jwt: str) -> list[dict]:
    """Return all teacher profiles (any status) except the admin themselves."""
    authed = _authed_client(admin_jwt)
    return (
        authed.table("teacher_profiles")
        .select("id, full_name, email, department, role, status, requested_at, reviewed_at")
        .neq("role", "admin")
        .order("requested_at", desc=True)
        .execute()
        .data
    )


def update_teacher_status(user_id: str, new_status: str,
                          reviewer_id: str, admin_jwt: str) -> None:
    """Set a teacher's approval status. new_status must be 'approved' or 'rejected'."""
    if new_status not in ("approved", "rejected"):
        raise ValueError(f"Invalid status: {new_status}")

    authed = _authed_client(admin_jwt)
    authed.table("teacher_profiles").update({
        "status":      new_status,
        "reviewed_at": "now()",
        "reviewed_by": reviewer_id,
    }).eq("id", user_id).execute()


# ── Exams ─────────────────────────────────────────────────────────────────────

def create_exam(teacher_id: str, exam_name: str, pass_threshold: float,
                roll_prefix: str, starting_roll: int,
                questions: list[dict], jwt: str) -> tuple[str, dict[int, str]]:
    """
    Insert one exam record and its questions for the given teacher.

    Returns (exam_id, question_id_map) where question_id_map maps
    question_number -> question UUID.
    """
    authed = _authed_client(jwt)

    exam_row = authed.table("exams").insert({
        "teacher_id":     teacher_id,
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
    authed.table("questions").insert(question_rows).execute()

    question_id_map = get_question_id_map(exam_id, jwt)
    return exam_id, question_id_map


def get_exam_with_questions(exam_id: str, jwt: str) -> dict | None:
    """Return exam record plus its questions list, or None if not found."""
    authed = _authed_client(jwt)
    rows = (
        authed.table("exams")
        .select("*, questions(*)")
        .eq("id", exam_id)
        .execute()
        .data
    )
    if not rows:
        return None
    exam = rows[0]
    # Normalize questions to the format expected by process_image
    exam["questions"] = [
        {
            "no":       q["question_number"],
            "clo":      q["clo_number"],
            "maxMarks": float(q["max_marks"]),
        }
        for q in sorted(exam.get("questions", []), key=lambda q: q["question_number"])
    ]
    return exam


def get_teacher_exams(jwt: str) -> list[dict]:
    """Return all exams for the authenticated teacher, ordered newest first."""
    authed = _authed_client(jwt)
    return (
        authed.table("exams")
        .select("id, name, pass_threshold, roll_prefix, created_at")
        .order("created_at", desc=True)
        .execute()
        .data
    )


def get_question_id_map(exam_id: str, jwt: str) -> dict[int, str]:
    """Return {question_number: question_uuid} for an exam."""
    authed = _authed_client(jwt)
    rows = (
        authed.table("questions")
        .select("id, question_number")
        .eq("exam_id", exam_id)
        .execute()
        .data
    )
    return {row["question_number"]: row["id"] for row in rows}


# ── Student results ───────────────────────────────────────────────────────────

def save_student_result(exam_id: str, student_roll_no: str,
                        marks: list[dict],
                        question_id_map: dict[int, str],
                        jwt: str) -> str:
    """
    Upsert a student and save their marks for one exam.

    Returns the UUID of the exam_results record.
    """
    authed = _authed_client(jwt)

    # Upsert student (roll_no is unique; get existing or create new)
    existing = (
        authed.table("students")
        .select("id")
        .eq("roll_no", student_roll_no)
        .execute()
        .data
    )

    if existing:
        student_id: str = existing[0]["id"]
    else:
        student_id = (
            authed.table("students")
            .insert({"roll_no": student_roll_no})
            .execute()
            .data[0]["id"]
        )

    result_row = (
        authed.table("exam_results")
        .insert({"exam_id": exam_id, "student_id": student_id})
        .execute()
        .data[0]
    )
    result_id: str = result_row["id"]

    mark_rows = []
    for m in marks:
        q_no = int(m["questionNo"])
        q_id = question_id_map.get(q_no)
        if q_id is None:
            continue
        conf = m.get("confidence")
        mark_rows.append({
            "result_id":      result_id,
            "question_id":    q_id,
            "obtained_marks": float(m.get("obtained", 0)),
            "ocr_confidence": float(conf) if conf is not None else None,
        })

    if mark_rows:
        authed.table("mark_entries").insert(mark_rows).execute()

    return result_id
