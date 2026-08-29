"""
Unit tests for Magic Link authentication, sessions, privacy isolation, and security controls.
"""

import pytest
from fastapi.testclient import TestClient
from trip_planner.api import db
from trip_planner.api.app import app


@pytest.fixture
def test_db(tmp_path):
    """Creates a temporary isolated SQLite database for testing."""
    db_file = tmp_path / "test_auth.db"
    db.init_db(db_path=db_file)
    return db_file


def test_magic_token_lifecycle(test_db):
    email = "traveler@example.com"
    token = db.create_login_token(email, ttl_seconds=900, db_path=test_db)
    assert len(token) > 20

    # Verify and consume token
    verified_email = db.verify_and_consume_login_token(token, db_path=test_db)
    assert verified_email == email

    # Token cannot be reused (one-time use)
    reused = db.verify_and_consume_login_token(token, db_path=test_db)
    assert reused is None


def test_expired_magic_token(test_db):
    email = "expired@example.com"
    # Create token with -1 sec TTL (already expired)
    token = db.create_login_token(email, ttl_seconds=-1, db_path=test_db)
    verified = db.verify_and_consume_login_token(token, db_path=test_db)
    assert verified is None


def test_session_lifecycle(test_db):
    email = "user@example.com"
    session_token = db.create_session(email, ttl_seconds=604800, db_path=test_db)
    assert len(session_token) > 20

    # Retrieve valid session
    session_email = db.get_session_email(session_token, db_path=test_db)
    assert session_email == email

    # Delete session (logout)
    db.delete_session(session_token, db_path=test_db)
    deleted_email = db.get_session_email(session_token, db_path=test_db)
    assert deleted_email is None


def test_user_job_privacy_isolation(test_db):
    user_a = "user_a@example.com"
    user_b = "user_b@example.com"

    # Create job for User A
    db.create_job("job-a-101", job_type="plan", status="complete", user_email=user_a, db_path=test_db)
    db.update_job("job-a-101", status="complete", result={"destination_city": "Goa"}, db_path=test_db)

    # Create job for User B
    db.create_job("job-b-202", job_type="plan", status="complete", user_email=user_b, db_path=test_db)
    db.update_job("job-b-202", status="complete", result={"destination_city": "Manali"}, db_path=test_db)

    # Create anonymous job
    db.create_job("job-anon-303", job_type="plan", status="complete", user_email=None, db_path=test_db)
    db.update_job("job-anon-303", status="complete", result={"destination_city": "Kochi"}, db_path=test_db)

    # User A strictly sees only job_a
    jobs_a = db.get_user_jobs(user_a, db_path=test_db)
    assert len(jobs_a) == 1
    assert jobs_a[0]["job_id"] == "job-a-101"

    # User B strictly sees only job_b
    jobs_b = db.get_user_jobs(user_b, db_path=test_db)
    assert len(jobs_b) == 1
    assert jobs_b[0]["job_id"] == "job-b-202"


def test_request_login_endpoint(monkeypatch, caplog):
    client = TestClient(app)
    # Ensure RESEND_API_KEY is unset to verify local warning guard
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    response = client.post("/api/auth/request-login", json={"email": "dev@example.com"})
    assert response.status_code == 200
    assert "magic login link has been sent" in response.json()["message"]

    # Confirm loud security warning in caplog
    assert any("[SECURITY WARNING] RESEND_API_KEY is NOT" in rec.message for rec in caplog.records)
