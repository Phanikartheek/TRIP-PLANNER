"""
Comprehensive test suite for Phase 1-15 production hardening safeguards:
- Input validation boundaries and string sanitization
- AI output validation, schema enforcement, and mathematical reconciliation
- Safe error categorization and information leak prevention
- Job deduplication and zombie reaper
- Security boundaries (XSS tags, body size limit, 413 / 429 status codes)
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from trip_planner.api import db
from trip_planner.api.app import (
    MAX_REQUEST_BODY_SIZE,
    _check_in_flight_duplicate,
    _register_in_flight_request,
    app,
    categorize_ai_error,
)
from trip_planner.schemas.models import (
    SmartRequest,
    TripPlanRequest,
    validate_and_reconcile_itinerary,
)


@pytest.fixture
def client():
    return TestClient(app)


# ==========================================
# 1. INPUT VALIDATION TESTS
# ==========================================

def test_input_valid_normal_trip():
    req = TripPlanRequest(
        origin="Bengaluru",
        cities="Goa",
        interests="beaches, seafood, historical forts",
        trip_length=3,
        budget=15000,
        travelers=2,
    )
    assert req.origin == "Bengaluru"
    assert req.cities == "Goa"
    assert req.trip_length == 3
    assert req.budget == 15000.0
    assert req.travelers == 2


@pytest.mark.parametrize("empty_val", ["", "   ", "\t"])
def test_input_rejects_empty_origin_and_cities(empty_val):
    with pytest.raises(ValidationError):
        TripPlanRequest(origin=empty_val, cities="Goa", interests="beaches")
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="Delhi", cities=empty_val, interests="beaches")


def test_input_rejects_oversized_fields():
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="A" * 105, cities="Goa", interests="beaches")
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="Delhi", cities="B" * 205, interests="beaches")
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="Delhi", cities="Goa", interests="C" * 505)
    with pytest.raises(ValidationError):
        SmartRequest(text="D" * 605)


@pytest.mark.parametrize("bad_budget", [-100, 0, 100, 499, 150000000])
def test_input_rejects_unrealistic_budgets(bad_budget):
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="Delhi", cities="Goa", interests="beaches", budget=bad_budget)


@pytest.mark.parametrize("bad_duration", [0, -1, 31, 100])
def test_input_rejects_invalid_duration(bad_duration):
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="Delhi", cities="Goa", interests="beaches", trip_length=bad_duration)


@pytest.mark.parametrize("bad_travelers", [0, -2, 21, 50])
def test_input_rejects_invalid_travelers(bad_travelers):
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="Delhi", cities="Goa", interests="beaches", travelers=bad_travelers)


@pytest.mark.parametrize("xss_payload", [
    "<script>alert(1)</script>",
    "javascript:void(0)",
    "<img src=x onerror=alert(1)>",
    "<iframe src='evil.com'></iframe>",
])
def test_input_rejects_malicious_script_tags(xss_payload):
    with pytest.raises(ValidationError):
        TripPlanRequest(origin=xss_payload, cities="Goa", interests="beaches")
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="Delhi", cities=xss_payload, interests="beaches")
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="Delhi", cities="Goa", interests=xss_payload)
    with pytest.raises(ValidationError):
        SmartRequest(text=xss_payload)


def test_input_rejects_control_characters():
    bad_string = "Delhi\x00\x07City"
    with pytest.raises(ValidationError):
        TripPlanRequest(origin=bad_string, cities="Goa", interests="beaches")


def test_input_rejects_pure_punctuation():
    with pytest.raises(ValidationError):
        TripPlanRequest(origin="!@#$%", cities="Goa", interests="beaches")


# ==========================================
# 2. AI OUTPUT VALIDATION & RECONCILIATION
# ==========================================

def test_output_validation_reconciles_costs_and_per_person():
    raw_itinerary = {
        "destination_city": "Visakhapatnam",
        "destination_country": "India",
        "trip_length_days": 2,
        "currency": "INR",
        "travelers": 2,
        "days": [
            {
                "day_number": 1,
                "theme": "Coastal Heritage",
                "morning": "Submarine museum",
                "afternoon": "Kailasagiri hills",
                "evening": "RK Beach",
                "estimated_cost": 500,  # Deliberately inconsistent with breakdown
                "cost_breakdown": [
                    {"item": "Museum pass", "amount": 200},
                    {"item": "Ropeway & snacks", "amount": 800},
                ],
            },
            {
                "day_number": 2,
                "theme": "Beaches & Dining",
                "morning": "Rushikonda beach",
                "afternoon": "Local Andhra Thali",
                "evening": "Lighthouse",
                "estimated_cost": 2000,
                "cost_breakdown": [
                    {"item": "Beach activities", "amount": 1000},
                    {"item": "Thali dinner", "amount": 500},
                ],
            },
        ],
    }

    validated = validate_and_reconcile_itinerary(
        raw_itinerary,
        expected_destination="Visakhapatnam",
        expected_trip_length=2,
        expected_travelers=2,
        expected_budget=10000,
    )

    # Day 1 cost breakdown sum: 200 + 800 = 1000
    assert validated.days[0].estimated_cost == 1000.0
    # Day 2 cost breakdown sum: 1000 + 500 = 1500
    assert validated.days[1].estimated_cost == 1500.0
    # Total cost sum: 1000 + 1500 = 2500
    assert validated.total_estimated_cost == 2500.0
    # Cost per person for 2 travelers: 2500 / 2 = 1250
    assert validated.cost_per_person == 1250.0
    # Within budget: no budget exceeded warning
    assert validated.budget_exceeded_warning is None


def test_output_validation_destination_mismatch_repair():
    raw_itinerary = {
        "destination_city": "Mumbai",  # Model hallucinated Mumbai instead of Goa
        "destination_country": "India",
        "trip_length_days": 1,
        "days": [
            {
                "day_number": 1,
                "theme": "Beach Tour",
                "morning": "Beach walk",
                "afternoon": "Shack lunch",
                "evening": "Sunset point",
                "estimated_cost": 1200,
            }
        ],
    }

    validated = validate_and_reconcile_itinerary(
        raw_itinerary,
        expected_destination="Goa",
        expected_trip_length=1,
    )
    assert validated.destination_city == "Goa"


def test_output_validation_day_count_trim_and_missing_failure():
    raw_extra_days = {
        "destination_city": "Goa",
        "trip_length_days": 3,
        "days": [
            {"day_number": 1, "theme": "D1", "morning": "M", "afternoon": "A", "evening": "E", "estimated_cost": 500},
            {"day_number": 2, "theme": "D2", "morning": "M", "afternoon": "A", "evening": "E", "estimated_cost": 500},
            {"day_number": 3, "theme": "D3", "morning": "M", "afternoon": "A", "evening": "E", "estimated_cost": 500},
        ],
    }
    # Slices to requested 2 days
    validated = validate_and_reconcile_itinerary(raw_extra_days, expected_trip_length=2)
    assert len(validated.days) == 2
    assert validated.trip_length_days == 2

    raw_few_days = {
        "destination_city": "Goa",
        "days": [
            {"day_number": 1, "theme": "D1", "morning": "M", "afternoon": "A", "evening": "E", "estimated_cost": 500},
        ],
    }
    # Fails if fewer days returned than requested and strict validation is enabled
    with pytest.raises(ValueError, match="incomplete itinerary"):
        validate_and_reconcile_itinerary(raw_few_days, expected_trip_length=3, strict_day_count=True)


def test_output_validation_budget_overrun_alert():
    raw_itinerary = {
        "destination_city": "Manali",
        "days": [
            {"day_number": 1, "theme": "Snow point", "morning": "M", "afternoon": "A", "evening": "E", "estimated_cost": 15000},
        ],
    }
    validated = validate_and_reconcile_itinerary(
        raw_itinerary,
        expected_destination="Manali",
        expected_trip_length=1,
        expected_budget=8000.0,
    )
    assert validated.total_estimated_cost == 15000.0
    assert validated.budget_exceeded_warning is not None
    assert "exceeds your requested budget" in validated.budget_exceeded_warning


# ==========================================
# 3. SAFE AI ERROR HANDLING
# ==========================================

def test_categorize_ai_error_clean_mappings():
    # Timeout
    msg_to = categorize_ai_error(asyncio.TimeoutError())
    assert "timed out" in msg_to.lower()

    # Rate limit
    msg_rl = categorize_ai_error(Exception("Rate limit 429 TPM exceeded on groq model"))
    assert "high demand" in msg_rl.lower()

    # Schema failure
    msg_schema = categorize_ai_error(Exception("ValidationError: malformed json response"))
    assert "could not be verified" in msg_schema.lower()

    # Network outage
    msg_net = categorize_ai_error(Exception("Connection refused by litellm API provider"))
    assert "temporarily unavailable" in msg_net.lower()

    # Unknown internal crash does NOT leak traceback
    msg_crash = categorize_ai_error(Exception("SyntaxError in /home/user/app/secret_core.py line 403"))
    assert "secret_core" not in msg_crash
    assert "line 403" not in msg_crash
    assert "unexpected error occurred" in msg_crash.lower()


# ==========================================
# 4. JOB SYSTEM & DEDUPLICATION
# ==========================================

def test_duplicate_in_flight_request_prevention():
    test_key = "127.0.0.1:delhi:goa:3:15000"
    job_id = "test-job-dedup-1"

    # Initially no duplicate
    assert _check_in_flight_duplicate(test_key) is None

    # Register in-flight job
    db.create_job(job_id=job_id, job_type="plan", status="running")
    _register_in_flight_request(test_key, job_id)

    # Second check within window returns existing job ID
    found_job_id = _check_in_flight_duplicate(test_key, window_sec=30.0)
    assert found_job_id == job_id


# ==========================================
# 5. SECURITY & SIZE LIMITS
# ==========================================

def test_request_body_size_limit(client):
    # Oversized payload exceeding 64KB
    oversized_data = {"text": "A" * (MAX_REQUEST_BODY_SIZE + 100)}
    headers = {"Content-Length": str(MAX_REQUEST_BODY_SIZE + 100), "Content-Type": "application/json"}

    response = client.post("/api/smart-request", json=oversized_data, headers=headers)
    assert response.status_code == 413
    assert "Payload Too Large" in response.json()["error"]
