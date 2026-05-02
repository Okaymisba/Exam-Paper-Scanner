"""
E2E conftest - starts the Flask application in a background thread so that
Playwright can make real HTTP requests against it during tests.

The server runs on a randomly assigned port. The base_url fixture provides
the full URL (e.g. http://localhost:54321) to each test.
"""

import os
import threading
import time

import pytest

# Ensure env vars exist before importing the Flask app.
os.environ.setdefault("FLASK_SECRET_KEY", "e2e-test-secret-key")
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "test-anon-key")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")

E2E_PORT = int(os.environ.get("E2E_PORT", "54321"))


@pytest.fixture(scope="session")
def flask_server():
    """
    Start the Flask dev server in a daemon thread for the entire test session.
    Returns the base URL string.
    """
    from unittest.mock import patch, MagicMock

    # Patch supabase at the module level so the app import does not fail even
    # if no real Supabase credentials are set.
    mock_supabase_client = MagicMock()
    mock_supabase_client.auth.get_user.return_value.user = None

    import app as flask_app

    flask_app.app.config["TESTING"] = True

    def _run():
        flask_app.app.run(port=E2E_PORT, use_reloader=False, threaded=True)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # Give the server a moment to start accepting connections.
    time.sleep(1.0)

    return f"http://localhost:{E2E_PORT}"


@pytest.fixture(scope="session")
def base_url(flask_server):
    """Provide the base URL of the running Flask server to individual tests."""
    return flask_server
