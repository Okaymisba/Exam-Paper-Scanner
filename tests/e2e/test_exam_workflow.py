"""
E2E tests for exam workflow API endpoints accessed from a browser context.

These tests verify that the exam-related API routes are reachable and return
the expected HTTP status codes when called via browser fetch requests.
The Flask server is started by the session-scoped flask_server fixture in
e2e/conftest.py.
"""

import pytest


# ---------------------------------------------------------------------------
# /api/exams
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_exams_endpoint_requires_auth_from_browser(page, base_url):
    """
    GET /api/exams without an Authorization header should return HTTP 401
    when called from a real browser context.
    """
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/exams');
            return { status: response.status, body: await response.json() };
        }
    """)
    assert result["status"] == 401
    assert "error" in result["body"]


@pytest.mark.e2e
def test_exams_endpoint_with_invalid_token_returns_401(page, base_url):
    """
    GET /api/exams with an Authorization header containing an invalid token
    should return HTTP 401 when called from a browser.
    """
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/exams', {
                headers: { 'Authorization': 'Bearer clearly-invalid-token' }
            });
            return { status: response.status };
        }
    """)
    assert result["status"] == 401


# ---------------------------------------------------------------------------
# /api/setup
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_setup_endpoint_requires_auth_from_browser(page, base_url):
    """
    POST /api/setup without Authorization should return HTTP 401 from
    a real browser fetch.
    """
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/setup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    examName: 'E2E Test Exam',
                    questions: [{ no: 1, clo: 1, maxMarks: 10 }],
                    passThreshold: 50,
                    rollPrefix: 'CS',
                    startingRoll: 1
                })
            });
            return { status: response.status };
        }
    """)
    assert result["status"] == 401


@pytest.mark.e2e
def test_setup_endpoint_missing_fields_returns_non_200(page, base_url):
    """
    POST /api/setup with a missing required field and no valid token should
    not return HTTP 200.
    """
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/setup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ examName: 'Incomplete' })
            });
            return { status: response.status };
        }
    """)
    assert result["status"] != 200


# ---------------------------------------------------------------------------
# /api/save_student
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_save_student_requires_auth_from_browser(page, base_url):
    """
    POST /api/save_student without Authorization should return HTTP 401
    when called from a browser fetch.
    """
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/save_student', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    examId: 'exam-001',
                    rollNo: 'CS001',
                    marks: []
                })
            });
            return { status: response.status };
        }
    """)
    assert result["status"] == 401


# ---------------------------------------------------------------------------
# /api/export
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_export_requires_auth_from_browser(page, base_url):
    """
    POST /api/export without Authorization should return HTTP 401 from
    a browser context.
    """
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    students: [],
                    setup: { examName: 'Test', passThreshold: 50, questions: [] }
                })
            });
            return { status: response.status };
        }
    """)
    assert result["status"] == 401


@pytest.mark.e2e
def test_export_missing_setup_without_auth_returns_401(page, base_url):
    """
    POST /api/export with no setup and no auth should return HTTP 401
    (auth check runs before input validation in the decorator order).
    """
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ students: [] })
            });
            return { status: response.status };
        }
    """)
    assert result["status"] == 401


# ---------------------------------------------------------------------------
# /api/admin/teachers
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_admin_teachers_requires_auth_from_browser(page, base_url):
    """
    GET /api/admin/teachers without Authorization should return HTTP 401
    from a browser context.
    """
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/admin/teachers');
            return { status: response.status };
        }
    """)
    assert result["status"] == 401


@pytest.mark.e2e
def test_admin_approve_requires_auth_from_browser(page, base_url):
    """
    POST /api/admin/approve without Authorization should return HTTP 401
    from a browser context.
    """
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/admin/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userId: 'some-id' })
            });
            return { status: response.status };
        }
    """)
    assert result["status"] == 401
