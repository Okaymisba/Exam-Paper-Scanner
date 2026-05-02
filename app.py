from flask import Flask, render_template, request, jsonify, send_file, session
from functools import wraps
from io import BytesIO
from datetime import datetime
import os
import tempfile

from ocr_processor import process_image
from excel_exporter import export_to_excel
import database

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "exam-marks-obe-secret-2024")


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return None


def require_auth(f):
    """Decorator: validates Bearer JWT and ensures account is approved."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        jwt = _bearer_token()
        if not jwt:
            return jsonify({"error": "Unauthorized"}), 401
        try:
            profile = database.get_current_user(jwt)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": "Authentication failed"}), 401
        request.user_jwt     = jwt
        request.user_id      = profile["id"]
        request.user_profile = profile
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    """Decorator: validates Bearer JWT and ensures account has admin role."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        jwt = _bearer_token()
        if not jwt:
            return jsonify({"error": "Unauthorized"}), 401
        try:
            from supabase import create_client
            client = create_client(
                os.environ["NEXT_PUBLIC_SUPABASE_URL"],
                os.environ["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"],
            )
            user_response = client.auth.get_user(jwt)
            user = user_response.user
            if not user:
                return jsonify({"error": "Invalid token"}), 401

            authed = create_client(
                os.environ["NEXT_PUBLIC_SUPABASE_URL"],
                os.environ["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"],
            )
            authed.postgrest.auth(jwt)
            rows = (
                authed.table("teacher_profiles")
                .select("id, full_name, role, status")
                .eq("id", user.id)
                .execute()
                .data
            )
            if not rows or rows[0]["role"] != "admin":
                return jsonify({"error": "Admin access required"}), 403

            request.user_jwt     = jwt
            request.user_id      = user.id
            request.user_profile = rows[0]
        except Exception as exc:
            return jsonify({"error": "Authentication failed"}), 401
        return f(*args, **kwargs)
    return wrapper


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.route("/api/auth/signup", methods=["POST"])
def api_signup():
    data       = request.get_json(force=True)
    email      = (data.get("email") or "").strip()
    password   = (data.get("password") or "").strip()
    full_name  = (data.get("fullName") or "").strip()
    department = (data.get("department") or "").strip()

    if not email or not password or not full_name:
        return jsonify({"error": "Email, password, and name are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    try:
        result = database.sign_up(email, password, full_name, department)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    if not result["success"]:
        return jsonify({"error": result["message"]}), 400

    return jsonify(result)


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data     = request.get_json(force=True)
    email    = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    try:
        result = database.sign_in(email, password)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 403
    except Exception as exc:
        return jsonify({"error": "Login failed. Please try again."}), 500

    return jsonify(result)


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def api_me():
    return jsonify({"profile": request.user_profile})


# ── Admin endpoints ───────────────────────────────────────────────────────────

@app.route("/api/admin/teachers", methods=["GET"])
@require_admin
def api_admin_teachers():
    try:
        teachers = database.get_all_teachers(request.user_jwt)
        return jsonify({"teachers": teachers})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/admin/approve", methods=["POST"])
@require_admin
def api_admin_approve():
    data    = request.get_json(force=True)
    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "Missing userId"}), 400
    try:
        database.update_teacher_status(user_id, "approved",
                                       request.user_id, request.user_jwt)
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/admin/reject", methods=["POST"])
@require_admin
def api_admin_reject():
    data    = request.get_json(force=True)
    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "Missing userId"}), 400
    try:
        database.update_teacher_status(user_id, "rejected",
                                       request.user_id, request.user_jwt)
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Exam history ──────────────────────────────────────────────────────────────

@app.route("/api/exams", methods=["GET"])
@require_auth
def api_exams():
    try:
        exams = database.get_teacher_exams(request.user_jwt)
        return jsonify({"exams": exams})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Exam workflow ─────────────────────────────────────────────────────────────

@app.route("/api/setup", methods=["POST"])
@require_auth
def api_setup():
    data     = request.get_json(force=True)
    required = ["examName", "questions", "passThreshold", "rollPrefix", "startingRoll"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    if not data["questions"]:
        return jsonify({"error": "At least one question required"}), 400

    try:
        exam_id, question_id_map = database.create_exam(
            teacher_id=request.user_id,
            exam_name=data["examName"],
            pass_threshold=float(data["passThreshold"]),
            roll_prefix=data["rollPrefix"],
            starting_roll=int(data["startingRoll"]),
            questions=data["questions"],
            jwt=request.user_jwt,
        )
    except Exception as exc:
        print(f"[DB] create_exam failed: {exc}")
        exam_id, question_id_map = None, {}

    return jsonify({
        "success":       True,
        "examId":        exam_id,
        "questionIdMap": question_id_map,
    })


@app.route("/api/upload", methods=["POST"])
@require_auth
def api_upload():
    """
    Accept a single image (field: image) and an examId (field: examId).
    Run OCR and return extracted achieved marks.
    """
    exam_id = request.form.get("examId", "").strip()
    if not exam_id:
        return jsonify({"error": "examId is required"}), 400

    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"error": "No image uploaded"}), 400

    # Fetch exam config from DB so we know questions and their max marks
    try:
        exam = database.get_exam_with_questions(exam_id, request.user_jwt)
    except Exception as exc:
        return jsonify({"error": f"Could not fetch exam config: {exc}"}), 500

    if not exam:
        return jsonify({"error": "Exam not found"}), 404

    # Build setup_config in the format process_image expects
    setup_config = {
        "examName":      exam["name"],
        "passThreshold": float(exam["pass_threshold"]),
        "rollPrefix":    exam["roll_prefix"],
        "questions":     [
            {"no": q["no"], "clo": q["clo"], "maxMarks": q["maxMarks"]}
            for q in exam["questions"]
        ],
    }

    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            file.save(f)
        result = process_image(tmp_path, setup_config)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.route("/api/save_student", methods=["POST"])
@require_auth
def api_save_student():
    """Persist one student's marks to Supabase."""
    data    = request.get_json(force=True)
    exam_id = (data.get("examId") or "").strip()
    roll_no = (data.get("rollNo") or "").strip()
    marks   = data.get("marks", [])

    if not exam_id or not roll_no:
        return jsonify({"error": "examId and rollNo are required"}), 400

    try:
        question_id_map = database.get_question_id_map(exam_id, request.user_jwt)
        result_id = database.save_student_result(
            exam_id=exam_id,
            student_roll_no=roll_no,
            marks=marks,
            question_id_map=question_id_map,
            jwt=request.user_jwt,
        )
        return jsonify({"success": True, "resultId": result_id})
    except Exception as exc:
        print(f"[DB] save_student failed for {roll_no}: {exc}")
        return jsonify({"success": True, "saved": False, "error": str(exc)})


@app.route("/api/export", methods=["POST"])
@require_auth
def api_export():
    data      = request.get_json(force=True)
    students  = data.get("students", [])
    setup_cfg = data.get("setup", {})

    if not setup_cfg:
        return jsonify({"error": "setup config required"}), 400

    exam_name = setup_cfg.get("examName", "Exam").replace(" ", "_")
    date_str  = datetime.now().strftime("%Y-%m-%d")
    filename  = f"{exam_name}_Marks_{date_str}.xlsx"

    buffer = BytesIO()
    try:
        export_to_excel(buffer, students, setup_cfg)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
