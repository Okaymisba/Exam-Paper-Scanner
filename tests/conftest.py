"""
Top-level conftest for the exam-marks-app test suite.

Sets required environment variables before any application module is imported,
so the Flask app and database module do not crash during collection.
"""

import os
import pytest

# Set environment variables before importing app or database modules.
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "test-anon-key")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")


# ---------------------------------------------------------------------------
# Shared profile fixtures used across integration and e2e test files
# ---------------------------------------------------------------------------

APPROVED_TEACHER_PROFILE = {
    "id": "teacher-uuid-001",
    "full_name": "Alice Smith",
    "email": "alice@example.com",
    "department": "Computer Science",
    "role": "teacher",
    "status": "approved",
}

ADMIN_PROFILE = {
    "id": "admin-uuid-001",
    "full_name": "Admin User",
    "email": "admin@example.com",
    "department": "Administration",
    "role": "admin",
    "status": "approved",
}

SAMPLE_EXAM = {
    "id": "exam-uuid-001",
    "name": "Midterm 2024",
    "pass_threshold": 50.0,
    "roll_prefix": "CS",
    "starting_roll": 1,
    "created_at": "2024-01-15T10:00:00",
    "questions": [
        {"no": 1, "clo": 1, "maxMarks": 10.0},
        {"no": 2, "clo": 1, "maxMarks": 10.0},
        {"no": 3, "clo": 2, "maxMarks": 20.0},
    ],
}

SAMPLE_STUDENTS = [
    {
        "resultId": "result-uuid-001",
        "rollNo": "CS001",
        "name": "Bob",
        "marks": [
            {"questionNo": 1, "clo": 1, "maxMarks": 10.0, "obtained": 8.0},
            {"questionNo": 2, "clo": 1, "maxMarks": 10.0, "obtained": 7.0},
            {"questionNo": 3, "clo": 2, "maxMarks": 20.0, "obtained": 15.0},
        ],
    },
    {
        "resultId": "result-uuid-002",
        "rollNo": "CS002",
        "name": "Carol",
        "marks": [
            {"questionNo": 1, "clo": 1, "maxMarks": 10.0, "obtained": 4.0},
            {"questionNo": 2, "clo": 1, "maxMarks": 10.0, "obtained": 3.0},
            {"questionNo": 3, "clo": 2, "maxMarks": 20.0, "obtained": 6.0},
        ],
    },
]


@pytest.fixture()
def app():
    """Create and configure a Flask test application instance."""
    import app as flask_app

    flask_app.app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key-for-pytest",
        }
    )
    yield flask_app.app


@pytest.fixture()
def client(app):
    """Return a Flask test client for making HTTP requests."""
    return app.test_client()


@pytest.fixture()
def approved_teacher_profile():
    """Return a sample approved teacher profile dict."""
    return APPROVED_TEACHER_PROFILE.copy()


@pytest.fixture()
def admin_profile():
    """Return a sample admin profile dict."""
    return ADMIN_PROFILE.copy()


@pytest.fixture()
def sample_exam():
    """Return a sample exam dict that includes questions."""
    return SAMPLE_EXAM.copy()


@pytest.fixture()
def sample_students():
    """Return a list of sample student result dicts."""
    return [s.copy() for s in SAMPLE_STUDENTS]


@pytest.fixture()
def auth_headers():
    """Return HTTP headers carrying a fake Bearer token."""
    return {"Authorization": "Bearer fake-jwt-token"}
