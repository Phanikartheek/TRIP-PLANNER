"""
Unit tests for multilingual language validation in request schemas and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from trip_planner.api.app import app
from trip_planner.schemas.models import DestinationQuestion, RevisionRequest, TripPlanRequest


def test_schema_language_validation_supported():
    """Test that supported language codes ('en', 'te', 'hi') are accepted and normalized."""
    req_en = TripPlanRequest(
        origin="Bengaluru",
        cities="Goa",
        interests="beaches",
        language="en"
    )
    assert req_en.language == "en"

    req_te = TripPlanRequest(
        origin="Hyderabad",
        cities="Vijayawada",
        interests="temples",
        language="TE "
    )
    assert req_te.language == "te"

    req_hi = TripPlanRequest(
        origin="Delhi",
        cities="Manali",
        interests="mountains",
        language="HI"
    )
    assert req_hi.language == "hi"

    qa_req = DestinationQuestion(
        job_id="test-job-id",
        question="Where to eat biryani?",
        language="te"
    )
    assert qa_req.language == "te"

    rev_req = RevisionRequest(
        job_id="test-job-id",
        feedback="Make day 2 cheaper",
        language="hi"
    )
    assert rev_req.language == "hi"


def test_schema_language_validation_unsupported_rejected():
    """Test that unsupported language codes (e.g., 'fr', 'de', 'es') raise a clear ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        TripPlanRequest(
            origin="Bengaluru",
            cities="Goa",
            interests="beaches",
            language="fr"
        )
    assert "Unsupported language code 'fr'" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info_qa:
        DestinationQuestion(
            job_id="test-job-id",
            question="What to do?",
            language="de"
        )
    assert "Unsupported language code 'de'" in str(exc_info_qa.value)


def test_api_endpoint_language_validation():
    """Test that FastAPI returns 422 Unprocessable Entity when an unsupported language is submitted."""
    client = TestClient(app)
    response = client.post(
        "/api/plan-trip",
        json={
            "origin": "Bengaluru",
            "cities": "Goa",
            "interests": "beaches",
            "trip_length": 3,
            "budget": 15000,
            "currency": "INR",
            "travel_mode": "domestic",
            "language": "fr"
        }
    )
    assert response.status_code == 422
    data = response.json()
    assert "Unsupported language code 'fr'" in str(data)
