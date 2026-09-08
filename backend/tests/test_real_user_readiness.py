"""
Production Regression Tests for Real-User Readiness:
- AI concurrency & active generation limits per client
- Deterministic full-parameter deduplication without leaking across users
- Data grounding classifications (verified_external, ai_estimate, ai_recommendation)
- Temporal logic and geographic sanity checks
- Trusted reverse proxy IP resolution
- Metrics endpoint observability
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from trip_planner.api.app import app, job_repo
from trip_planner.api.db import init_db
from trip_planner.api.metrics import metrics
from trip_planner.schemas.models import validate_and_reconcile_itinerary


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path):
    old_db_path = job_repo.db_path
    test_db = tmp_path / "test_readiness.db"
    init_db(db_path=test_db)
    job_repo.db_path = test_db
    metrics.reset()
    yield test_db
    job_repo.db_path = old_db_path


@pytest.fixture
def client():
    return TestClient(app)


def test_data_grounding_schema_and_defaults():
    """Verifies that TripItinerary includes explicit FieldGrounding metadata without fabricated data."""
    raw = {
        "destination_city": "Jaipur",
        "trip_length_days": 2,
        "days": [
            {
                "day_number": 1,
                "theme": "Palaces and Forts",
                "morning": "Amber Fort exploration and Elephant ride.",
                "afternoon": "City Palace and museum tour.",
                "evening": "Hawa Mahal views and market shopping.",
                "estimated_cost": 3000.0,
            },
            {
                "day_number": 2,
                "theme": "Astronomy and Culture",
                "morning": "Jantar Mantar observatory.",
                "afternoon": "Albert Hall Museum.",
                "evening": "Chokhi Dhani cultural village and dinner.",
                "estimated_cost": 3500.0,
            },
        ],
    }
    itin = validate_and_reconcile_itinerary(raw, expected_destination="Jaipur", expected_trip_length=2)
    assert itin.data_grounding is not None
    assert "weather_forecast" in itin.data_grounding
    assert itin.data_grounding["weather_forecast"].source_type == "verified_external"
    assert itin.data_grounding["estimated_costs"].source_type == "ai_estimate"
    assert itin.data_grounding["daily_itinerary"].source_type == "ai_recommendation"
    assert itin.data_grounding["emergency_contacts"].source_type == "verified_external"


def test_temporal_logic_deduplication():
    """Verifies that identical morning and afternoon activities are deterministically differentiated."""
    raw = {
        "destination_city": "Kochi",
        "trip_length_days": 1,
        "days": [
            {
                "day_number": 1,
                "theme": "Colonial Heritage",
                "morning": "Fort Kochi walking tour",
                "afternoon": "Fort Kochi walking tour",  # Exact duplicate
                "evening": "Chinese fishing nets sunset",
                "estimated_cost": 2000.0,
            }
        ],
    }
    itin = validate_and_reconcile_itinerary(raw, expected_destination="Kochi", expected_trip_length=1)
    day1 = itin.days[0]
    assert day1.morning != day1.afternoon
    assert "Afternoon" in day1.afternoon


def test_per_client_active_generation_throttling(client):
    """Verifies that a client with an active running job receives 429 when attempting to launch another."""
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk-mock-key", "TRUST_PROXY": "true"}), \
         patch("trip_planner.api.app._execute_trip_job", return_value=None):
        # Create an active pending job for this client IP
        client_ip = "198.51.100.5"
        job_repo.create_job(
            job_id="active-job-1",
            job_type="plan",
            status="running",
            client_ip=client_ip,
        )

        res = client.post(
            "/api/plan-trip",
            json={
                "origin": "Bengaluru",
                "cities": "Mysuru",
                "interests": "Palaces, gardens",
                "trip_length": 2,
                "budget": 10000.0,
                "travelers": 1,
                "language": "en",
            },
            headers={"X-Forwarded-For": client_ip},
        )
        assert res.status_code == 429
        assert "already have a trip generation in progress" in res.json()["detail"]


def test_deterministic_deduplication_returns_existing_job(client):
    """Verifies that an identical request from the same client returns the existing job instead of spawning a new one."""
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk-mock-key", "TRUST_PROXY": "true"}), \
         patch("trip_planner.api.app._execute_trip_job", return_value=None):
        payload = {
            "origin": "Chennai",
            "cities": "Puducherry",
            "interests": "French colony, beaches",
            "trip_length": 3,
            "budget": 15000.0,
            "currency": "INR",
            "travelers": 2,
            "language": "en",
        }
        client_ip = "198.51.100.10"
        headers = {"X-Forwarded-For": client_ip}

        # First request creates the job
        res1 = client.post("/api/plan-trip", json=payload, headers=headers)
        assert res1.status_code == 200
        job_id_1 = res1.json()["job_id"]

        # Second request with identical payload from SAME client should return existing job_id
        res2 = client.post("/api/plan-trip", json=payload, headers=headers)
        assert res2.status_code == 200
        assert res2.json()["job_id"] == job_id_1


def test_deduplication_does_not_leak_across_different_clients(client):
    """Verifies that User A's identical trip parameters are never returned to User B."""
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk-mock-key", "TRUST_PROXY": "true"}), \
         patch("trip_planner.api.app._execute_trip_job", return_value=None):
        payload = {
            "origin": "Delhi",
            "cities": "Agra",
            "interests": "Taj Mahal",
            "trip_length": 1,
            "budget": 5000.0,
            "currency": "INR",
            "travelers": 1,
            "language": "en",
        }

        # User A from IP A
        res1 = client.post("/api/plan-trip", json=payload, headers={"X-Forwarded-For": "198.51.100.20"})
        assert res1.status_code == 200
        job_id_1 = res1.json()["job_id"]

        # User B from IP B (different client)
        res2 = client.post("/api/plan-trip", json=payload, headers={"X-Forwarded-For": "198.51.100.21"})
        assert res2.status_code == 200
        job_id_2 = res2.json()["job_id"]

        # Must be distinct job IDs - no cross-tenant leakage!
        assert job_id_1 != job_id_2


def test_metrics_endpoint(client):
    """Verifies /api/metrics exposes operational metrics and zero secrets."""
    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "total_requests" in data
    assert "successful_generations" in data
    assert "failed_generations" in data
    assert "generation_latency_seconds" in data
    assert "p95" in data["generation_latency_seconds"]
    assert "max_concurrent_ai_jobs" in data

    # Verify zero secrets in metrics output
    data_str = json.dumps(data)
    assert "api_key" not in data_str
    assert "password" not in data_str
    assert "secret" not in data_str
