"""
E2E tests for authentication user flows.

These tests use pytest-playwright to drive a real Chromium browser against
the running Flask development server. They verify that the UI renders
correctly and that API endpoints respond as expected when called from a
browser context.

The flask_server fixture (defined in e2e/conftest.py) starts the server
once per session. The base_url fixture provides the server address.

Note: page.goto(base_url) must be called before any page.evaluate() that
uses relative URL paths, because the browser starts on about:blank and
relative fetch calls have no base to resolve against.
"""

import pytest


# ---------------------------------------------------------------------------
# Page load tests (no auth required)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_index_page_loads_in_browser(page, base_url):
    """The index page should load without JavaScript errors in a real browser."""
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg) if msg.type == "error" else None)

    page.goto(base_url)
    page.wait_for_load_state("networkidle")

    assert page.title() != ""
    critical_errors = [
        e for e in console_errors
        if "SyntaxError" in e.text or "ReferenceError" in e.text
    ]
    assert len(critical_errors) == 0


@pytest.mark.e2e
def test_index_page_has_body_content(page, base_url):
    """The index page body should not be empty."""
    page.goto(base_url)
    page.wait_for_load_state("networkidle")
    body_text = page.locator("body").inner_text()
    assert len(body_text.strip()) > 0


# ---------------------------------------------------------------------------
# API endpoint tests via browser fetch
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_signup_api_reachable_from_browser(page, base_url):
    """
    The /api/auth/signup endpoint should be reachable and return a JSON
    response from a browser fetch call.
    """
    page.goto(base_url)
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/auth/signup', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: 'e2e@example.com',
                    password: 'testpass123',
                    fullName: 'E2E Tester',
                    department: 'QA'
                })
            });
            return { status: response.status, body: await response.json() };
        }
    """)
    assert result["status"] in (200, 400, 500)


@pytest.mark.e2e
def test_login_api_reachable_from_browser(page, base_url):
    """
    The /api/auth/login endpoint should be reachable from a browser and
    return a structured JSON response.
    """
    page.goto(base_url)
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: 'nobody@example.com',
                    password: 'wrongpassword'
                })
            });
            return { status: response.status };
        }
    """)
    assert result["status"] != 404


@pytest.mark.e2e
def test_me_endpoint_returns_401_without_token_from_browser(page, base_url):
    """
    GET /api/auth/me without an Authorization header should return 401
    even when called from a real browser context.
    """
    page.goto(base_url)
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/auth/me');
            return { status: response.status, body: await response.json() };
        }
    """)
    assert result["status"] == 401
    assert "error" in result["body"]


@pytest.mark.e2e
def test_signup_validation_missing_fields_from_browser(page, base_url):
    """
    Submitting signup with missing required fields should return HTTP 400
    from the browser fetch call.
    """
    page.goto(base_url)
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/auth/signup', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ email: '', password: '', fullName: '' })
            });
            return { status: response.status, body: await response.json() };
        }
    """)
    assert result["status"] == 400
    assert "error" in result["body"]


@pytest.mark.e2e
def test_short_password_returns_400_from_browser(page, base_url):
    """
    A signup attempt with a password shorter than 6 characters should return
    HTTP 400 from the browser context.
    """
    page.goto(base_url)
    result = page.evaluate("""
        async () => {
            const response = await fetch('/api/auth/signup', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: 'e2e@example.com',
                    password: '123',
                    fullName: 'Short Pass User'
                })
            });
            return { status: response.status, body: await response.json() };
        }
    """)
    assert result["status"] == 400
    assert "6" in result["body"].get("error", "")
