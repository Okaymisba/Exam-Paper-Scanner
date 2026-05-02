"""
Integration tests for exam-history Flask routes.

Routes covered:
  GET    /api/exams
  GET    /api/exams/<exam_id>
  DELETE /api/exams/<exam_id>/students/<result_id>

All Supabase calls are mocked via database module patches.
"""

import json
from unittest.mock import patch

import pytest

from tests.conftest import APPROVED_TEACHER_PROFILE, SAMPLE_EXAM, SAMPLE_STUDENTS


AUTH_HEADERS = {"Authorization": "Bearer fake-jwt-token"}


# ---------------------------------------------------------------------------
# GET /api/exams
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_get_exams_returns_list_for_authenticated_teacher(client):
    """GET /api/exams should return HTTP 200 with the exams list."""
    exams = [
        {"id": "exam-001", "name": "Quiz 1", "pass_threshold": 50.0},
        {"id": "exam-002", "name": "Midterm", "pass_threshold": 60.0},
    ]
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.get_teacher_exams", return_value=exams):
            response = client.get("/api/exams", headers=AUTH_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert "exams" in body
    assert len(body["exams"]) == 2


@pytest.mark.integration
def test_get_exams_returns_empty_list_when_no_exams_exist(client):
    """GET /api/exams should return an empty list when the teacher has no exams."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.get_teacher_exams", return_value=[]):
            response = client.get("/api/exams", headers=AUTH_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["exams"] == []


@pytest.mark.integration
def test_get_exams_returns_401_without_auth(client):
    """GET /api/exams without Authorization header should return HTTP 401."""
    response = client.get("/api/exams")
    assert response.status_code == 401


@pytest.mark.integration
def test_get_exams_returns_500_on_db_error(client):
    """GET /api/exams should return HTTP 500 when the database layer raises."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.get_teacher_exams", side_effect=Exception("DB failure")):
            response = client.get("/api/exams", headers=AUTH_HEADERS)

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/exams/<exam_id>
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_get_single_exam_returns_exam_and_students(client):
    """GET /api/exams/<id> should return the exam config and student results."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.get_exam_with_questions", return_value=SAMPLE_EXAM):
            with patch("database.get_exam_students", return_value=SAMPLE_STUDENTS):
                response = client.get(
                    f"/api/exams/{SAMPLE_EXAM['id']}", headers=AUTH_HEADERS
                )

    assert response.status_code == 200
    body = response.get_json()
    assert "exam" in body
    assert "students" in body
    assert body["exam"]["name"] == "Midterm 2024"
    assert len(body["students"]) == 2


@pytest.mark.integration
def test_get_single_exam_returns_404_when_not_found(client):
    """GET /api/exams/<id> should return HTTP 404 when the exam does not exist."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.get_exam_with_questions", return_value=None):
            response = client.get("/api/exams/nonexistent-id", headers=AUTH_HEADERS)

    assert response.status_code == 404
    body = response.get_json()
    assert "error" in body


@pytest.mark.integration
def test_get_single_exam_returns_401_without_auth(client):
    """GET /api/exams/<id> without Authorization header should return HTTP 401."""
    response = client.get("/api/exams/some-exam-id")
    assert response.status_code == 401


@pytest.mark.integration
def test_get_single_exam_returns_500_on_db_error(client):
    """GET /api/exams/<id> should return HTTP 500 when the database raises."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch(
            "database.get_exam_with_questions", side_effect=Exception("DB error")
        ):
            response = client.get("/api/exams/exam-uuid-001", headers=AUTH_HEADERS)

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /api/exams/<exam_id>/students/<result_id>
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_delete_student_returns_success(client):
    """DELETE /api/exams/<id>/students/<result_id> should return success=True."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch("database.delete_student_result") as mock_delete:
            response = client.delete(
                "/api/exams/exam-uuid-001/students/result-uuid-001",
                headers=AUTH_HEADERS,
            )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    mock_delete.assert_called_once_with("result-uuid-001", "fake-jwt-token")


@pytest.mark.integration
def test_delete_student_returns_401_without_auth(client):
    """DELETE without Authorization should return HTTP 401."""
    response = client.delete("/api/exams/exam-uuid-001/students/result-uuid-001")
    assert response.status_code == 401


@pytest.mark.integration
def test_delete_student_returns_500_on_db_error(client):
    """DELETE should return HTTP 500 when database.delete_student_result raises."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        with patch(
            "database.delete_student_result", side_effect=Exception("Cascade failed")
        ):
            response = client.delete(
                "/api/exams/exam-uuid-001/students/result-uuid-001",
                headers=AUTH_HEADERS,
            )

    assert response.status_code == 500
    body = response.get_json()
    assert "error" in body
