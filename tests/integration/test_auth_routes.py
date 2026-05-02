"""
Integration tests for authentication-related Flask routes.

Routes covered:
  GET  /                  (index page)
  POST /api/auth/signup
  POST /api/auth/login
  GET  /api/auth/me

All Supabase calls are mocked so no real network connection is required.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import APPROVED_TEACHER_PROFILE


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_index_route_returns_200(client):
    """The index route should return HTTP 200 with HTML content."""
    response = client.get("/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/auth/signup
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_signup_success(client):
    """A valid signup payload should return HTTP 200 with success=True."""
    signup_result = {
        "success": True,
        "message": "Request submitted. Pending admin approval.",
        "needs_confirmation": False,
    }
    with patch("database.sign_up", return_value=signup_result):
        response = client.post(
            "/api/auth/signup",
            data=json.dumps({
                "email": "newteacher@example.com",
                "password": "securepassword",
                "fullName": "New Teacher",
                "department": "Physics",
            }),
            content_type="application/json",
        )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True


@pytest.mark.integration
def test_signup_missing_email_returns_400(client):
    """Signup without an email should return HTTP 400 with a descriptive error."""
    response = client.post(
        "/api/auth/signup",
        data=json.dumps({"password": "pass1234", "fullName": "No Email"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert "error" in body


@pytest.mark.integration
def test_signup_missing_password_returns_400(client):
    """Signup without a password should return HTTP 400 with an error."""
    response = client.post(
        "/api/auth/signup",
        data=json.dumps({"email": "a@b.com", "fullName": "No Pass"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert "error" in body


@pytest.mark.integration
def test_signup_short_password_returns_400(client):
    """A password shorter than 6 characters should return HTTP 400."""
    response = client.post(
        "/api/auth/signup",
        data=json.dumps({
            "email": "a@b.com",
            "password": "123",
            "fullName": "Short Pass",
        }),
        content_type="application/json",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert "6" in body.get("error", "")


@pytest.mark.integration
def test_signup_missing_full_name_returns_400(client):
    """Signup without fullName should return HTTP 400."""
    response = client.post(
        "/api/auth/signup",
        data=json.dumps({"email": "a@b.com", "password": "pass1234"}),
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.integration
def test_signup_database_exception_returns_400(client):
    """If database.sign_up raises an exception, the route should return HTTP 400."""
    with patch("database.sign_up", side_effect=Exception("Supabase error")):
        response = client.post(
            "/api/auth/signup",
            data=json.dumps({
                "email": "a@b.com",
                "password": "goodpass",
                "fullName": "Error Case",
            }),
            content_type="application/json",
        )
    assert response.status_code == 400
    body = response.get_json()
    assert "error" in body


@pytest.mark.integration
def test_signup_database_returns_failure_dict(client):
    """If database.sign_up returns success=False, the route should return HTTP 400."""
    fail_result = {"success": False, "message": "Email already in use."}
    with patch("database.sign_up", return_value=fail_result):
        response = client.post(
            "/api/auth/signup",
            data=json.dumps({
                "email": "taken@example.com",
                "password": "goodpass",
                "fullName": "Duplicate",
            }),
            content_type="application/json",
        )
    assert response.status_code == 400
    body = response.get_json()
    assert "error" in body


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_login_success(client):
    """Valid credentials should return HTTP 200 with access_token and profile."""
    login_result = {
        "success": True,
        "access_token": "jwt-access-token",
        "refresh_token": "jwt-refresh-token",
        "profile": APPROVED_TEACHER_PROFILE,
    }
    with patch("database.sign_in", return_value=login_result):
        response = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "alice@example.com", "password": "pass123"}),
            content_type="application/json",
        )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "access_token" in body


@pytest.mark.integration
def test_login_missing_email_returns_400(client):
    """Login without an email should return HTTP 400."""
    response = client.post(
        "/api/auth/login",
        data=json.dumps({"password": "pass123"}),
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.integration
def test_login_missing_password_returns_400(client):
    """Login without a password should return HTTP 400."""
    response = client.post(
        "/api/auth/login",
        data=json.dumps({"email": "alice@example.com"}),
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.integration
def test_login_invalid_credentials_returns_403(client):
    """Invalid credentials (ValueError from database) should return HTTP 403."""
    with patch("database.sign_in", side_effect=ValueError("Incorrect email or password.")):
        response = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "wrong@example.com", "password": "wrongpass"}),
            content_type="application/json",
        )
    assert response.status_code == 403
    body = response.get_json()
    assert "error" in body


@pytest.mark.integration
def test_login_generic_exception_returns_500(client):
    """An unexpected exception from database.sign_in should return HTTP 500."""
    with patch("database.sign_in", side_effect=Exception("Unexpected DB error")):
        response = client.post(
            "/api/auth/login",
            data=json.dumps({"email": "a@b.com", "password": "pass123"}),
            content_type="application/json",
        )
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_me_returns_profile_for_authenticated_user(client):
    """GET /api/auth/me should return the user profile when a valid JWT is supplied."""
    with patch("database.get_current_user", return_value=APPROVED_TEACHER_PROFILE):
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer fake-jwt-token"},
        )
    assert response.status_code == 200
    body = response.get_json()
    assert "profile" in body
    assert body["profile"]["id"] == APPROVED_TEACHER_PROFILE["id"]


@pytest.mark.integration
def test_me_returns_401_without_auth_header(client):
    """GET /api/auth/me without an Authorization header should return HTTP 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    body = response.get_json()
    assert "error" in body


@pytest.mark.integration
def test_me_returns_403_when_account_not_approved(client):
    """GET /api/auth/me should return HTTP 403 when the account status is not approved."""
    with patch("database.get_current_user", side_effect=ValueError("Account status: pending")):
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer pending-user-jwt"},
        )
    assert response.status_code == 403
    body = response.get_json()
    assert "error" in body


@pytest.mark.integration
def test_me_returns_401_when_jwt_is_invalid(client):
    """GET /api/auth/me should return HTTP 401 when the JWT cannot be verified."""
    with patch("database.get_current_user", side_effect=Exception("Token verification failed")):
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer bad-jwt"},
        )
    assert response.status_code == 401
