"""
Unit tests for the database module.

All Supabase network calls are mocked so these tests run entirely offline.
Each test patches 'database.create_client' (the symbol imported at module
load time) and drives the public database functions through their logic.
"""

from unittest.mock import MagicMock, patch, call

import pytest

import database


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_client():
    """Return a MagicMock that behaves like a Supabase client."""
    return MagicMock()


def _chain(client_mock, table_name, data):
    """
    Set up the common fluent-builder chain on a mock client so that:
        client.table(table_name).select(...).eq(...).execute().data
    returns `data`.
    """
    (
        client_mock.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = data
    return client_mock


# ---------------------------------------------------------------------------
# sign_up
# ---------------------------------------------------------------------------


@pytest.mark.unit
@patch("database.create_client")
def test_sign_up_returns_success_for_regular_teacher(mock_create):
    """sign_up should return success=True and a pending-status message for a new teacher."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client

    mock_user = MagicMock()
    mock_user.id = "user-uuid-001"
    mock_client.auth.sign_up.return_value.user = mock_user
    mock_client.auth.sign_up.return_value.session = None

    # Insert chain - just needs to not raise
    (
        mock_client.table.return_value
        .insert.return_value
        .execute.return_value
        .data
    ) = [{"id": "user-uuid-001"}]

    result = database.sign_up("teacher@example.com", "password123", "Alice", "CS")

    assert result["success"] is True
    assert "pending" in result["message"].lower() or "submitted" in result["message"].lower()


@pytest.mark.unit
@patch("database.create_client")
def test_sign_up_returns_failure_when_no_user_returned(mock_create):
    """sign_up should return success=False if Supabase returns no user object."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client
    mock_client.auth.sign_up.return_value.user = None

    result = database.sign_up("bad@example.com", "pass", "Name", "Dept")

    assert result["success"] is False


@pytest.mark.unit
@patch("database.create_client")
def test_sign_up_admin_email_gets_approved_status(mock_create):
    """A signup with the configured ADMIN_EMAIL should get an 'approved' success message."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client

    mock_user = MagicMock()
    mock_user.id = "admin-uuid-001"
    mock_client.auth.sign_up.return_value.user = mock_user

    # Give the admin a session so the authed client path runs
    mock_session = MagicMock()
    mock_session.access_token = "admin-access-token"
    mock_client.auth.sign_up.return_value.session = mock_session

    (
        mock_client.table.return_value
        .insert.return_value
        .execute.return_value
        .data
    ) = [{"id": "admin-uuid-001"}]

    result = database.sign_up("admin@example.com", "admin123", "Admin User", "Admin")

    assert result["success"] is True
    # Admin message should not mention pending approval
    assert "pending" not in result["message"].lower()


# ---------------------------------------------------------------------------
# sign_in
# ---------------------------------------------------------------------------


@pytest.mark.unit
@patch("database.create_client")
def test_sign_in_returns_tokens_and_profile_on_success(mock_create):
    """sign_in should return access_token, refresh_token, and profile for valid creds."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client

    mock_user = MagicMock()
    mock_user.id = "user-uuid-001"

    mock_session = MagicMock()
    mock_session.access_token = "access-token-abc"
    mock_session.refresh_token = "refresh-token-xyz"

    mock_client.auth.sign_in_with_password.return_value.session = mock_session
    mock_client.auth.sign_in_with_password.return_value.user = mock_user

    profile = {
        "id": "user-uuid-001",
        "full_name": "Alice Smith",
        "email": "alice@example.com",
        "department": "CS",
        "role": "teacher",
        "status": "approved",
    }

    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = [profile]

    result = database.sign_in("alice@example.com", "password123")

    assert result["success"] is True
    assert result["access_token"] == "access-token-abc"
    assert result["profile"]["status"] == "approved"


@pytest.mark.unit
@patch("database.create_client")
def test_sign_in_raises_value_error_for_pending_account(mock_create):
    """sign_in should raise ValueError when the teacher account is still pending."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client

    mock_user = MagicMock()
    mock_user.id = "user-uuid-002"

    mock_session = MagicMock()
    mock_session.access_token = "access-token"
    mock_session.refresh_token = "refresh-token"

    mock_client.auth.sign_in_with_password.return_value.session = mock_session
    mock_client.auth.sign_in_with_password.return_value.user = mock_user

    pending_profile = {
        "id": "user-uuid-002",
        "full_name": "Bob",
        "email": "bob@example.com",
        "department": "Math",
        "role": "teacher",
        "status": "pending",
    }
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = [pending_profile]

    with pytest.raises(ValueError, match="pending"):
        database.sign_in("bob@example.com", "password123")


@pytest.mark.unit
@patch("database.create_client")
def test_sign_in_raises_value_error_for_rejected_account(mock_create):
    """sign_in should raise ValueError when the teacher account has been rejected."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client

    mock_user = MagicMock()
    mock_user.id = "user-uuid-003"

    mock_session = MagicMock()
    mock_session.access_token = "access-token"
    mock_session.refresh_token = "refresh-token"

    mock_client.auth.sign_in_with_password.return_value.session = mock_session
    mock_client.auth.sign_in_with_password.return_value.user = mock_user

    rejected_profile = {
        "id": "user-uuid-003",
        "full_name": "Carol",
        "email": "carol@example.com",
        "department": "Eng",
        "role": "teacher",
        "status": "rejected",
    }
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = [rejected_profile]

    with pytest.raises(ValueError, match="not approved"):
        database.sign_in("carol@example.com", "password123")


@pytest.mark.unit
@patch("database.create_client")
def test_sign_in_raises_value_error_when_no_session_returned(mock_create):
    """sign_in should raise ValueError when Supabase returns no session."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client
    mock_client.auth.sign_in_with_password.return_value.session = None

    with pytest.raises(ValueError):
        database.sign_in("nobody@example.com", "wrongpassword")


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------


@pytest.mark.unit
@patch("database.create_client")
def test_get_current_user_returns_profile_for_valid_jwt(mock_create):
    """get_current_user should return the profile dict for a valid JWT."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client

    mock_user = MagicMock()
    mock_user.id = "user-uuid-001"
    mock_client.auth.get_user.return_value.user = mock_user

    profile = {
        "id": "user-uuid-001",
        "full_name": "Alice",
        "email": "alice@example.com",
        "department": "CS",
        "role": "teacher",
        "status": "approved",
    }
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = [profile]

    result = database.get_current_user("valid-jwt")

    assert result["id"] == "user-uuid-001"
    assert result["status"] == "approved"


@pytest.mark.unit
@patch("database.create_client")
def test_get_current_user_raises_value_error_for_invalid_jwt(mock_create):
    """get_current_user should raise ValueError when the JWT resolves to no user."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client
    mock_client.auth.get_user.return_value.user = None

    with pytest.raises(ValueError, match="Invalid or expired"):
        database.get_current_user("bad-jwt")


@pytest.mark.unit
@patch("database.create_client")
def test_get_current_user_raises_for_non_approved_status(mock_create):
    """get_current_user should raise ValueError for non-approved account status."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client

    mock_user = MagicMock()
    mock_user.id = "user-uuid-pending"
    mock_client.auth.get_user.return_value.user = mock_user

    pending_profile = {
        "id": "user-uuid-pending",
        "full_name": "Dan",
        "email": "dan@example.com",
        "department": "Bio",
        "role": "teacher",
        "status": "pending",
    }
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = [pending_profile]

    with pytest.raises(ValueError, match="status"):
        database.get_current_user("valid-jwt-for-pending-user")


# ---------------------------------------------------------------------------
# update_teacher_status
# ---------------------------------------------------------------------------


@pytest.mark.unit
@patch("database.create_client")
def test_update_teacher_status_raises_for_invalid_status(mock_create):
    """update_teacher_status should raise ValueError for unrecognised status strings."""
    with pytest.raises(ValueError, match="Invalid status"):
        database.update_teacher_status("some-id", "suspended", "admin-id", "admin-jwt")


@pytest.mark.unit
@patch("database.create_client")
def test_update_teacher_status_calls_supabase_update(mock_create):
    """update_teacher_status should invoke the correct table update on the authed client."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client

    update_chain = mock_client.table.return_value.update.return_value.eq.return_value.execute
    update_chain.return_value = MagicMock()

    database.update_teacher_status("teacher-id-001", "approved", "admin-id-001", "admin-jwt")

    mock_client.table.assert_called_with("teacher_profiles")
    assert update_chain.called


# ---------------------------------------------------------------------------
# create_exam
# ---------------------------------------------------------------------------


@pytest.mark.unit
@patch("database.create_client")
def test_create_exam_returns_exam_id_and_question_id_map(mock_create):
    """create_exam should return a tuple of (exam_id, question_id_map)."""
    mock_client = _mock_client()
    mock_create.return_value = mock_client

    # Exam insert returns new row with id
    (
        mock_client.table.return_value
        .insert.return_value
        .execute.return_value
        .data
    ) = [{"id": "exam-uuid-999"}]

    # get_question_id_map -> questions table select
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = [
        {"id": "q-uuid-001", "question_number": 1},
        {"id": "q-uuid-002", "question_number": 2},
    ]

    questions = [
        {"no": 1, "clo": 1, "maxMarks": 10},
        {"no": 2, "clo": 2, "maxMarks": 20},
    ]

    exam_id, q_map = database.create_exam(
        teacher_id="teacher-uuid-001",
        exam_name="Quiz 1",
        pass_threshold=50.0,
        roll_prefix="CS",
        starting_roll=1,
        questions=questions,
        jwt="teacher-jwt",
    )

    assert exam_id == "exam-uuid-999"
    assert isinstance(q_map, dict)
