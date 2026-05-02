"""
Integration tests for exam workflow Flask routes.

Routes covered:
  POST /api/setup
  POST /api/upload
  POST /api/save_student
  POST /api/export

All Supabase, OCR, and file-system calls are mocked.
"""

import io
import json
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import APPROVED_TEACHER_PROFILE, SAMPLE_EXAM, SAMPLE_STUDENTS


AUTH_HEADERS = {"Authorization": "Bearer fake-jwt-token"}

VALID_SETUP_PAYLOAD = {
    "examName": "Final Exam",
    "questions": [
        {"no": 1, "clo": 1, "maxMarks": 10},
        {"no": 2, "clo": 2, "maxMarks": 20},
    ],
    "passThreshold": 50.0,
    "rollPrefix": "CS",
    "startingRoll": 1,
}


# ---------------------------------------------------------------------------
# POST /api/setup
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_setup_creates_exam_and_returns_exam_id(client):
    """POST /api/setup with a valid payload should return examId and questionIdMap."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch(
            "database.create_exam",
            return_value=("exam-uuid-new", {1: "q-uuid-001", 2: "q-uuid-002"}),
        ):
            response = client.post(
                "/api/setup",
                data=json.dumps(VALID_SETUP_PAYLOAD),
                content_type="application/json",
                headers=AUTH_HEADERS,
            )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["examId"] == "exam-uuid-new"
    assert body["questionIdMap"] is not None


@pytest.mark.integration
def test_setup_missing_exam_name_returns_400(client):
    """POST /api/setup without examName should return HTTP 400."""
    payload = {k: v for k, v in VALID_SETUP_PAYLOAD.items() if k != "examName"}
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        response = client.post(
            "/api/setup",
            data=json.dumps(payload),
            content_type="application/json",
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400
    body = response.get_json()
    assert "examName" in body.get("error", "")


@pytest.mark.integration
def test_setup_empty_questions_list_returns_400(client):
    """POST /api/setup with an empty questions list should return HTTP 400."""
    payload = {**VALID_SETUP_PAYLOAD, "questions": []}
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        response = client.post(
            "/api/setup",
            data=json.dumps(payload),
            content_type="application/json",
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400
    body = response.get_json()
    assert "question" in body.get("error", "").lower()


@pytest.mark.integration
def test_setup_returns_401_without_auth(client):
    """POST /api/setup without Authorization header should return HTTP 401."""
    response = client.post(
        "/api/setup",
        data=json.dumps(VALID_SETUP_PAYLOAD),
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_setup_missing_pass_threshold_returns_400(client):
    """POST /api/setup without passThreshold should return HTTP 400."""
    payload = {k: v for k, v in VALID_SETUP_PAYLOAD.items() if k != "passThreshold"}
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        response = client.post(
            "/api/setup",
            data=json.dumps(payload),
            content_type="application/json",
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400


@pytest.mark.integration
def test_setup_db_failure_still_returns_200_with_null_exam_id(client):
    """
    If database.create_exam raises, the route catches the error and still
    returns HTTP 200 with examId=None and an empty questionIdMap.
    """
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.create_exam", side_effect=Exception("DB failure")):
            response = client.post(
                "/api/setup",
                data=json.dumps(VALID_SETUP_PAYLOAD),
                content_type="application/json",
                headers=AUTH_HEADERS,
            )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["examId"] is None


# ---------------------------------------------------------------------------
# POST /api/upload
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_upload_missing_exam_id_returns_400(client):
    """POST /api/upload without examId form field should return HTTP 400."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        data = {"image": (io.BytesIO(b"fake image data"), "test.jpg")}
        response = client.post(
            "/api/upload",
            data=data,
            content_type="multipart/form-data",
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400
    body = response.get_json()
    assert "examId" in body.get("error", "")


@pytest.mark.integration
def test_upload_missing_image_returns_400(client):
    """POST /api/upload without an image file should return HTTP 400."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        response = client.post(
            "/api/upload",
            data={"examId": "exam-uuid-001"},
            content_type="multipart/form-data",
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400
    body = response.get_json()
    assert "image" in body.get("error", "").lower()


@pytest.mark.integration
def test_upload_exam_not_found_returns_404(client):
    """POST /api/upload when exam is not found should return HTTP 404."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.get_exam_with_questions", return_value=None):
            data = {
                "examId": "nonexistent-exam",
                "image": (io.BytesIO(b"fake image data"), "test.jpg"),
            }
            response = client.post(
                "/api/upload",
                data=data,
                content_type="multipart/form-data",
                headers=AUTH_HEADERS,
            )
    assert response.status_code == 404


@pytest.mark.integration
def test_upload_returns_401_without_auth(client):
    """POST /api/upload without Authorization header should return HTTP 401."""
    data = {
        "examId": "exam-uuid-001",
        "image": (io.BytesIO(b"fake image data"), "test.jpg"),
    }
    response = client.post(
        "/api/upload",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_upload_successful_ocr_returns_result(client):
    """POST /api/upload with a valid image and exam should return OCR results."""
    ocr_result = {
        "rollNo": "CS001",
        "marks": [
            {"questionNo": 1, "obtained": 8, "confidence": 0.95},
        ],
    }
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.get_exam_with_questions", return_value=SAMPLE_EXAM):
            with patch("app.process_image", return_value=ocr_result):
                data = {
                    "examId": SAMPLE_EXAM["id"],
                    "image": (io.BytesIO(b"fake image bytes"), "sheet.jpg"),
                }
                response = client.post(
                    "/api/upload",
                    data=data,
                    content_type="multipart/form-data",
                    headers=AUTH_HEADERS,
                )
    assert response.status_code == 200
    body = response.get_json()
    assert "marks" in body or "rollNo" in body


# ---------------------------------------------------------------------------
# POST /api/save_student
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_save_student_returns_result_id(client):
    """POST /api/save_student with valid payload should return resultId."""
    payload = {
        "examId": "exam-uuid-001",
        "rollNo": "CS001",
        "marks": [{"questionNo": 1, "obtained": 8, "confidence": 0.95}],
    }
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.get_question_id_map", return_value={1: "q-uuid-001"}):
            with patch("database.save_student_result", return_value="result-uuid-new"):
                response = client.post(
                    "/api/save_student",
                    data=json.dumps(payload),
                    content_type="application/json",
                    headers=AUTH_HEADERS,
                )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["resultId"] == "result-uuid-new"


@pytest.mark.integration
def test_save_student_missing_exam_id_returns_400(client):
    """POST /api/save_student without examId should return HTTP 400."""
    payload = {"rollNo": "CS001", "marks": []}
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        response = client.post(
            "/api/save_student",
            data=json.dumps(payload),
            content_type="application/json",
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400


@pytest.mark.integration
def test_save_student_missing_roll_no_returns_400(client):
    """POST /api/save_student without rollNo should return HTTP 400."""
    payload = {"examId": "exam-uuid-001", "marks": []}
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        response = client.post(
            "/api/save_student",
            data=json.dumps(payload),
            content_type="application/json",
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400


@pytest.mark.integration
def test_save_student_db_error_returns_200_with_saved_false(client):
    """
    If the database raises while saving, save_student should still return
    HTTP 200 but with saved=False and an error message.
    """
    payload = {
        "examId": "exam-uuid-001",
        "rollNo": "CS001",
        "marks": [{"questionNo": 1, "obtained": 8}],
    }
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.get_question_id_map", side_effect=Exception("DB error")):
            response = client.post(
                "/api/save_student",
                data=json.dumps(payload),
                content_type="application/json",
                headers=AUTH_HEADERS,
            )
    assert response.status_code == 200
    body = response.get_json()
    assert body.get("saved") is False or "error" in body


@pytest.mark.integration
def test_save_student_returns_401_without_auth(client):
    """POST /api/save_student without Authorization header should return HTTP 401."""
    payload = {"examId": "exam-001", "rollNo": "CS001", "marks": []}
    response = client.post(
        "/api/save_student",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/export
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_export_returns_xlsx_file(client):
    """POST /api/export with valid data should return an Excel file attachment."""
    payload = {
        "students": SAMPLE_STUDENTS,
        "setup": {
            "examName": "Test Exam",
            "passThreshold": 50,
            "questions": [
                {"no": 1, "clo": 1, "maxMarks": 10},
                {"no": 2, "clo": 1, "maxMarks": 10},
                {"no": 3, "clo": 2, "maxMarks": 20},
            ],
        },
    }
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        response = client.post(
            "/api/export",
            data=json.dumps(payload),
            content_type="application/json",
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    assert "spreadsheetml" in response.content_type


@pytest.mark.integration
def test_export_missing_setup_returns_400(client):
    """POST /api/export without a setup config should return HTTP 400."""
    payload = {"students": SAMPLE_STUDENTS}
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        response = client.post(
            "/api/export",
            data=json.dumps(payload),
            content_type="application/json",
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400
    body = response.get_json()
    assert "error" in body


@pytest.mark.integration
def test_export_returns_401_without_auth(client):
    """POST /api/export without Authorization header should return HTTP 401."""
    payload = {
        "students": [],
        "setup": {"examName": "Exam", "passThreshold": 50, "questions": []},
    }
    response = client.post(
        "/api/export",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_export_returns_500_when_exporter_raises(client):
    """POST /api/export should return HTTP 500 when export_to_excel raises."""
    payload = {
        "students": SAMPLE_STUDENTS,
        "setup": {
            "examName": "Broken Exam",
            "passThreshold": 50,
            "questions": [{"no": 1, "clo": 1, "maxMarks": 10}],
        },
    }
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("app.export_to_excel", side_effect=Exception("Export error")):
            response = client.post(
                "/api/export",
                data=json.dumps(payload),
                content_type="application/json",
                headers=AUTH_HEADERS,
            )
    assert response.status_code == 500
    body = response.get_json()
    assert "error" in body
