"""
Comprehensive verification tests for the 5 Production Readiness priorities:
1. AI Multi-Provider Fallback & Observability Metrics
2. 5-Stage Job Progress System & Schema Compatibility
3. SQLAlchemy Persistence Layer (PostgreSQL & SQLite)
4. Authentication, Session Management, and My Trips Claiming
5. Daily Plan Quota & Rate Limiting (429 Retry-After)
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from trip_planner.api import db
from trip_planner.api.app import DAILY_PLAN_LIMIT, app, job_repo
from trip_planner.api.metrics import metrics


@pytest.fixture
def client(tmp_path: Path):
    test_db = tmp_path / "readiness_test.db"
    orig_default = db.DEFAULT_DB_PATH
    db.DEFAULT_DB_PATH = test_db
    db.init_db(db_path=test_db)
    orig_db = getattr(job_repo, "db_path", None)
    job_repo.db_path = test_db
    test_client = TestClient(app)
    yield test_client
    job_repo.db_path = orig_db
    db.DEFAULT_DB_PATH = orig_default


def test_priority_1_fallback_metrics_tracking():
    """Verify that provider fallback occurrences are cleanly recorded in metrics."""
    metrics.reset()
    metrics.record_provider_fallback("groq/qwen/qwen3.8-27b", "groq/openai/gpt-oss-120b")
    metrics.record_provider_fallback("groq/openai/gpt-oss-120b", "openrouter/meta-llama/llama-3.3-70b-instruct")

    summary = metrics.get_metrics_summary()
    assert summary["fallbacks_total"] == 2
    assert "groq/qwen/qwen3.8-27b -> groq/openai/gpt-oss-120b" in summary["fallbacks_by_transition"]
    assert "groq/openai/gpt-oss-120b -> openrouter/meta-llama/llama-3.3-70b-instruct" in summary["fallbacks_by_transition"]


def test_priority_2_job_progress_stages_and_schema(client: TestClient, tmp_path: Path):
    """Verify that JobStatusResponse includes current_stage, progress_percentage, and message."""
    test_db = tmp_path / "readiness_test.db"
    job_id = "test-progress-job-1"
    
    # 1. Create job with initial stage
    db.create_job(
        job_id=job_id,
        job_type="plan",
        status="pending",
        current_stage="analyzing_request",
        progress_percentage=10,
        message="Analyzing destination constraints...",
        db_path=test_db,
    )

    res = client.get(f"/api/status/{job_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == job_id
    assert data["status"] == "pending"
    assert data["current_stage"] == "analyzing_request"
    assert data["progress_percentage"] == 10
    assert data["message"] == "Analyzing destination constraints..."

    # 2. Update to stage 3: checking_weather_local
    db.update_job(
        job_id=job_id,
        status="running",
        current_stage="checking_weather_local",
        progress_percentage=55,
        message="Checking weather & local gems...",
        db_path=test_db,
    )
    res = client.get(f"/api/status/{job_id}")
    data = res.json()
    assert data["status"] == "running"
    assert data["current_stage"] == "checking_weather_local"
    assert data["progress_percentage"] == 55

    # 3. Update to complete
    db.update_job(
        job_id=job_id,
        status="complete",
        current_stage="complete",
        progress_percentage=100,
        message="Itinerary ready!",
        result={"destination_city": "Goa", "total_estimated_cost": 15000},
        db_path=test_db,
    )
    res = client.get(f"/api/status/{job_id}")
    data = res.json()
    assert data["status"] == "complete"
    assert data["current_stage"] == "complete"
    assert data["progress_percentage"] == 100
    assert data["message"] == "Itinerary ready!"


def test_priority_3_sqlalchemy_persistence_and_postgres_url_normalization(tmp_path: Path):
    """Verify SQLAlchemy PostgreSQL URL normalization and zero-config SQLite persistence."""
    # Test URL normalization
    with patch.dict(os.environ, {"DATABASE_URL": "postgres://user:pass@ep-host.railway.internal:5432/railway"}):
        pg_url = db.get_database_url()
        assert pg_url.startswith("postgresql+psycopg://")
        assert "postgres://" not in pg_url

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@ep-host.railway.internal:5432/railway"}):
        pg_url2 = db.get_database_url()
        assert pg_url2.startswith("postgresql+psycopg://")

    # Test SQLite engine and table creation
    sqlite_db = tmp_path / "sqlite_test.db"
    engine = db.get_engine(db_path=sqlite_db)
    assert engine.dialect.name == "sqlite"
    db.init_db(db_path=sqlite_db)
    assert sqlite_db.exists()


def test_priority_4_auth_my_trips_and_claim(client: TestClient, tmp_path: Path):
    """Verify magic link token generation, session verification, My Trips retrieval, and trip claiming."""
    test_db = tmp_path / "readiness_test.db"
    user_email = "traveler@example.com"

    # 1. Create anonymous trip first
    anon_job_id = "anon-trip-999"
    db.create_job(
        job_id=anon_job_id,
        job_type="plan",
        status="complete",
        result={
            "destination_city": "Udaipur",
            "destination_country": "India",
            "trip_length_days": 3,
            "total_estimated_cost": 22000,
            "currency": "INR",
        },
        db_path=test_db,
    )

    # 2. Generate and verify login token with recent_job_id claim
    token = db.create_login_token(user_email, db_path=test_db)
    assert token is not None

    verify_res = client.post(
        "/api/auth/verify-token",
        json={"token": token, "recent_job_id": anon_job_id},
    )
    assert verify_res.status_code == 200
    assert "session_token" in verify_res.cookies

    # 3. Fetch /api/my-trips with session cookie
    my_trips_res = client.get("/api/my-trips")
    assert my_trips_res.status_code == 200
    data = my_trips_res.json()
    assert data["email"] == user_email
    assert len(data["trips"]) == 1
    assert data["trips"][0]["job_id"] == anon_job_id
    assert data["trips"][0]["destination_city"] == "Udaipur"

    # 4. Claim an additional trip via /api/my-trips/claim
    second_job_id = "anon-trip-888"
    db.create_job(
        job_id=second_job_id,
        job_type="plan",
        status="complete",
        result={"destination_city": "Manali", "total_estimated_cost": 18000},
        db_path=test_db,
    )

    claim_res = client.post("/api/my-trips/claim", json={"job_id": second_job_id})
    assert claim_res.status_code == 200

    # Verify both trips are now associated with user
    my_trips_res2 = client.get("/api/my-trips")
    assert len(my_trips_res2.json()["trips"]) == 2


def test_priority_5_daily_plan_quota_rate_limiting(client: TestClient, tmp_path: Path):
    """Verify that daily plan limit returns structured 429 with Retry-After when limit reached."""
    test_db = tmp_path / "readiness_test.db"
    client_key = "testclient"

    # Pre-populate usage up to the daily limit
    for _ in range(DAILY_PLAN_LIMIT):
        db.increment_daily_usage(client_key, db_path=test_db)

    assert db.get_daily_usage(client_key, db_path=test_db) == DAILY_PLAN_LIMIT

    # Attempt to plan another trip
    payload = {
        "origin": "Delhi",
        "cities": "Jaipur",
        "interests": "forts and culture",
        "trip_length": 2,
        "budget": 12000,
        "currency": "INR",
        "travelers": 1,
    }

    with patch("trip_planner.api.app._execute_trip_job") as mock_exec:
        res = client.post("/api/plan-trip", json=payload)
        assert res.status_code == 429
        assert "Retry-After" in res.headers
        assert res.headers["Retry-After"] == "86400"
        assert f"Daily limit of {DAILY_PLAN_LIMIT} trip plans reached" in res.json()["detail"]
        mock_exec.assert_not_called()
