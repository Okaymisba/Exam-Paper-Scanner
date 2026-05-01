from flask import Flask, render_template, request, jsonify, send_file
from io import BytesIO
from datetime import datetime
import os
import tempfile

from ocr_processor import process_image
from excel_exporter import export_to_excel
import database

app = Flask(__name__)
app.secret_key = "exam-marks-obe-secret-2024"

# In-memory config for the current exam session.
# Holds the exam setup plus the db-assigned exam_id and question_id_map
# so subsequent student-save calls can reference the right records.
_setup_config: dict = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/setup", methods=["POST"])
def api_setup():
    data = request.get_json(force=True)
    required = ["examName", "questions", "passThreshold", "rollPrefix", "startingRoll"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    if not data["questions"]:
        return jsonify({"error": "At least one question required"}), 400

    _setup_config.clear()
    _setup_config.update(data)

    # Persist exam to Supabase; keep going even if DB is unavailable.
    try:
        exam_id = database.create_exam(
            exam_name=data["examName"],
            pass_threshold=float(data["passThreshold"]),
            roll_prefix=data["rollPrefix"],
            starting_roll=int(data["startingRoll"]),
            questions=data["questions"],
        )
        _setup_config["_examId"] = exam_id
        _setup_config["_questionIdMap"] = database.get_question_id_map(exam_id)
    except Exception as exc:
        # Log the error but do not block the teacher from using the app.
        print(f"[DB] Failed to save exam to Supabase: {exc}")
        _setup_config["_examId"] = None
        _setup_config["_questionIdMap"] = {}

    return jsonify({"success": True})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    Accept a single image (field: image).
    Run OCR and return extracted achieved marks.
    Returns: { marks: [{questionNo, clo, maxMarks, obtained, confidence}] }
    """
    if not _setup_config:
        return jsonify({"error": "Setup not configured. Please complete setup first."}), 400

    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"error": "No image uploaded"}), 400

    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            file.save(f)
        result = process_image(tmp_path, _setup_config)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.route("/api/save_student", methods=["POST"])
def api_save_student():
    """
    Persist one student's marks to Supabase.
    Expects: { rollNo: str, marks: [{questionNo, obtained, confidence}] }
    """
    if not _setup_config:
        return jsonify({"error": "Setup not configured"}), 400

    exam_id = _setup_config.get("_examId")
    if not exam_id:
        # DB save was skipped during setup; return a soft success so the
        # frontend can continue without interruption.
        return jsonify({"success": True, "saved": False})

    data = request.get_json(force=True)
    roll_no = data.get("rollNo", "").strip()
    marks   = data.get("marks", [])

    if not roll_no:
        return jsonify({"error": "Missing rollNo"}), 400

    try:
        result_id = database.save_student_result(
            exam_id=exam_id,
            student_roll_no=roll_no,
            marks=marks,
            question_id_map=_setup_config.get("_questionIdMap", {}),
        )
        return jsonify({"success": True, "saved": True, "resultId": result_id})
    except Exception as exc:
        print(f"[DB] Failed to save student {roll_no}: {exc}")
        return jsonify({"success": True, "saved": False, "error": str(exc)})


@app.route("/api/export", methods=["POST"])
def api_export():
    if not _setup_config:
        return jsonify({"error": "Setup not configured"}), 400

    data     = request.get_json(force=True)
    students = data.get("students", [])

    exam_name = _setup_config.get("examName", "Exam").replace(" ", "_")
    date_str  = datetime.now().strftime("%Y-%m-%d")
    filename  = f"{exam_name}_Marks_{date_str}.xlsx"

    buffer = BytesIO()
    try:
        export_to_excel(buffer, students, _setup_config)
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
