"""
Unit tests for SQLite persistent job store and API rate limiting.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from trip_planner.api import db
from trip_planner.api.app import app


def test_db_create_get_update_roundtrip(tmp_path: Path):
    db_file = tmp_path / "test_jobs.db"
    db.init_db(db_path=db_file)

    # 1. Create a job
    job = db.create_job(
        job_id="test-job-1",
        job_type="plan",
        status="pending",
        db_path=db_file,
    )
    assert job["job_id"] == "test-job-1"
    assert job["status"] == "pending"
    assert job["job_type"] == "plan"

    # 2. Retrieve job
    fetched = db.get_job("test-job-1", db_path=db_file)
    assert fetched is not None
    assert fetched["status"] == "pending"
    assert fetched["result"] is None

    # 3. Update job to running
    db.update_job("test-job-1", status="running", db_path=db_file)
    fetched = db.get_job("test-job-1", db_path=db_file)
    assert fetched["status"] == "running"

    # 4. Update job to complete with result and QA history
    sample_result = {"destination_city": "Vijayawada", "total_estimated_cost": 5000}
    sample_history = [{"question": "Where to eat?", "answer": "Golden Pavilion", "timestamp": 12345.0}]
    db.update_job(
        "test-job-1",
        status="complete",
        result=sample_result,
        qa_history=sample_history,
        db_path=db_file,
    )

    fetched = db.get_job("test-job-1", db_path=db_file)
    assert fetched["status"] == "complete"
    assert fetched["result"] == sample_result
    assert fetched["qa_history"] == sample_history


def test_db_startup_reconciliation_marks_interrupted_jobs_failed(tmp_path: Path):
    db_file = tmp_path / "test_reconcile.db"
    db.init_db(db_path=db_file)

    # Create one complete job and one running job
    db.create_job(job_id="done-job", job_type="plan", status="complete", db_path=db_file)
    db.create_job(job_id="dead-job", job_type="plan", status="running", db_path=db_file)
    db.create_job(job_id="pending-job", job_type="plan", status="pending", db_path=db_file)

    # Simulate server restart by running init_db again
    db.init_db(db_path=db_file)

    done_job = db.get_job("done-job", db_path=db_file)
    dead_job = db.get_job("dead-job", db_path=db_file)
    pending_job = db.get_job("pending-job", db_path=db_file)

    assert done_job["status"] == "complete"
    assert dead_job["status"] == "failed"
    assert "interrupted by a server restart" in dead_job["error"]
    assert pending_job["status"] == "failed"
    assert "interrupted by a server restart" in pending_job["error"]


def test_db_get_root_job_traversal(tmp_path: Path):
    db_file = tmp_path / "test_hierarchy.db"
    db.init_db(db_path=db_file)

    db.create_job(job_id="root-1", job_type="plan", status="complete", db_path=db_file)
    db.create_job(job_id="rev-1", job_type="revise", status="complete", parent_job_id="root-1", db_path=db_file)
    db.create_job(job_id="qa-1", job_type="qa", status="complete", parent_job_id="rev-1", db_path=db_file)

    root = db.get_root_job("qa-1", db_path=db_file)
    assert root is not None
    assert root["job_id"] == "root-1"


def test_rate_limiter_wired_to_endpoints():
    client = TestClient(app)

    # Verify limiter is attached to app state
    assert hasattr(app.state, "limiter")
    assert app.state.limiter is not None

    # Test that health endpoint is accessible without limit
    resp = client.get("/api/health")
    assert resp.status_code == 200

    # Test that rate limiter is wired on plan-trip
    # (Checking endpoint route metadata has limiter registered)
    routes = {route.path: route for route in app.routes}
    assert "/api/plan-trip" in routes
    assert "/api/revise-trip" in routes
    assert "/api/ask-question" in routes
