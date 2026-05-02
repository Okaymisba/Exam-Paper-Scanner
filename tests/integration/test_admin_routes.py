"""
Integration tests for admin Flask routes.

Routes covered:
  GET  /api/admin/teachers
  POST /api/admin/approve
  POST /api/admin/reject

The require_admin decorator creates its own supabase.create_client call
inside the function body. We patch 'supabase.create_client' at the module
level so that both calls inside the decorator use the same mock, allowing us
to control the auth.get_user response and the teacher_profiles query.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import ADMIN_PROFILE, APPROVED_TEACHER_PROFILE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_admin_mock():
    """
    Build a mock supabase client that makes require_admin pass.

    The decorator makes two create_client calls:
      1. First client: client.auth.get_user(jwt) -> user object
      2. Second client (authed): table query returning admin profile row
    """
    mock_user = MagicMock()
    mock_user.id = ADMIN_PROFILE["id"]

    mock_client = MagicMock()
    mock_client.auth.get_user.return_value.user = mock_user

    # Table query for teacher_profiles returning admin profile
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = [ADMIN_PROFILE]

    return mock_client


# ---------------------------------------------------------------------------
# GET /api/admin/teachers
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_admin_teachers_returns_teacher_list(client):
    """GET /api/admin/teachers should return HTTP 200 with a list of teachers."""
    mock_client = _build_admin_mock()
    teacher_list = [
        {
            "id": "teacher-uuid-001",
            "full_name": "Alice Smith",
            "email": "alice@example.com",
            "role": "teacher",
            "status": "pending",
        }
    ]

    with patch("supabase.create_client", return_value=mock_client):
        with patch("database.get_all_teachers", return_value=teacher_list):
            response = client.get(
                "/api/admin/teachers",
                headers={"Authorization": "Bearer admin-jwt"},
            )

    assert response.status_code == 200
    body = response.get_json()
    assert "teachers" in body
    assert len(body["teachers"]) == 1


@pytest.mark.integration
def test_admin_teachers_returns_401_without_auth(client):
    """GET /api/admin/teachers without Authorization header should return HTTP 401."""
    response = client.get("/api/admin/teachers")
    assert response.status_code == 401
    body = response.get_json()
    assert "error" in body


@pytest.mark.integration
def test_admin_teachers_returns_403_for_non_admin(client):
    """GET /api/admin/teachers with a non-admin profile should return HTTP 403."""
    mock_user = MagicMock()
    mock_user.id = APPROVED_TEACHER_PROFILE["id"]

    mock_client = MagicMock()
    mock_client.auth.get_user.return_value.user = mock_user
    # Teacher role - not admin
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = [APPROVED_TEACHER_PROFILE]

    with patch("supabase.create_client", return_value=mock_client):
        response = client.get(
            "/api/admin/teachers",
            headers={"Authorization": "Bearer teacher-jwt"},
        )

    assert response.status_code == 403
    body = response.get_json()
    assert "Admin access required" in body.get("error", "")


@pytest.mark.integration
def test_admin_teachers_returns_401_when_user_is_none(client):
    """If the JWT resolves to no user, the admin endpoint should return HTTP 401."""
    mock_client = MagicMock()
    mock_client.auth.get_user.return_value.user = None

    with patch("supabase.create_client", return_value=mock_client):
        response = client.get(
            "/api/admin/teachers",
            headers={"Authorization": "Bearer bad-jwt"},
        )

    assert response.status_code == 401


@pytest.mark.integration
def test_admin_teachers_returns_500_on_db_error(client):
    """If database.get_all_teachers raises, the route should return HTTP 500."""
    mock_client = _build_admin_mock()

    with patch("supabase.create_client", return_value=mock_client):
        with patch("database.get_all_teachers", side_effect=Exception("DB error")):
            response = client.get(
                "/api/admin/teachers",
                headers={"Authorization": "Bearer admin-jwt"},
            )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/admin/approve
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_admin_approve_returns_success(client):
    """POST /api/admin/approve with a valid userId should return success=True."""
    mock_client = _build_admin_mock()

    with patch("supabase.create_client", return_value=mock_client):
        with patch("database.update_teacher_status") as mock_update:
            response = client.post(
                "/api/admin/approve",
                data=json.dumps({"userId": "teacher-uuid-001"}),
                content_type="application/json",
                headers={"Authorization": "Bearer admin-jwt"},
            )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    mock_update.assert_called_once_with(
        "teacher-uuid-001", "approved", ADMIN_PROFILE["id"], "admin-jwt"
    )


@pytest.mark.integration
def test_admin_approve_missing_user_id_returns_400(client):
    """POST /api/admin/approve without userId should return HTTP 400."""
    mock_client = _build_admin_mock()

    with patch("supabase.create_client", return_value=mock_client):
        response = client.post(
            "/api/admin/approve",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": "Bearer admin-jwt"},
        )

    assert response.status_code == 400
    body = response.get_json()
    assert "Missing userId" in body.get("error", "")


@pytest.mark.integration
def test_admin_approve_db_error_returns_500(client):
    """If update_teacher_status raises, approve should return HTTP 500."""
    mock_client = _build_admin_mock()

    with patch("supabase.create_client", return_value=mock_client):
        with patch("database.update_teacher_status", side_effect=Exception("DB error")):
            response = client.post(
                "/api/admin/approve",
                data=json.dumps({"userId": "teacher-uuid-001"}),
                content_type="application/json",
                headers={"Authorization": "Bearer admin-jwt"},
            )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/admin/reject
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_admin_reject_returns_success(client):
    """POST /api/admin/reject with a valid userId should return success=True."""
    mock_client = _build_admin_mock()

    with patch("supabase.create_client", return_value=mock_client):
        with patch("database.update_teacher_status") as mock_update:
            response = client.post(
                "/api/admin/reject",
                data=json.dumps({"userId": "teacher-uuid-002"}),
                content_type="application/json",
                headers={"Authorization": "Bearer admin-jwt"},
            )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    mock_update.assert_called_once_with(
        "teacher-uuid-002", "rejected", ADMIN_PROFILE["id"], "admin-jwt"
    )


@pytest.mark.integration
def test_admin_reject_missing_user_id_returns_400(client):
    """POST /api/admin/reject without userId should return HTTP 400."""
    mock_client = _build_admin_mock()

    with patch("supabase.create_client", return_value=mock_client):
        response = client.post(
            "/api/admin/reject",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": "Bearer admin-jwt"},
        )

    assert response.status_code == 400


@pytest.mark.integration
def test_admin_reject_without_auth_returns_401(client):
    """POST /api/admin/reject without an Authorization header should return HTTP 401."""
    response = client.post(
        "/api/admin/reject",
        data=json.dumps({"userId": "teacher-uuid-002"}),
        content_type="application/json",
    )
    assert response.status_code == 401
