"""
Unit tests for Part C: Routing Pattern.
Verifies:
- Intent classification accuracy across all 4 intent types (new_trip, revision, question, comparison)
- Extraction of parameters (cities, duration, budget, origin)
- POST /api/smart-request endpoint correctly routing without duplicating logic
"""

import pytest
from fastapi.testclient import TestClient
from trip_planner.api import db
from trip_planner.api.app import app
from trip_planner.patterns.router import IntentClassificationResult, TripRouter, UserIntent


@pytest.fixture
def client():
    db.init_db()
    return TestClient(app)


def test_classify_new_trip_intent():
    query = "Plan a 4-day trip to Varanasi under 15000 from Bengaluru"
    res = TripRouter.classify_intent(query)

    assert isinstance(res, IntentClassificationResult)
    assert res.intent == UserIntent.NEW_TRIP
    assert res.extracted_params["trip_length"] == 4
    assert res.extracted_params["budget"] == 15000.0
    assert "Varanasi" in res.extracted_params["cities"]
    assert res.extracted_params["origin"] == "Bengaluru"


def test_classify_revision_intent():
    query = "Make day 2 cheaper and replace the luxury resort with a budget hostel"
    res = TripRouter.classify_intent(query, has_active_job=True)

    assert isinstance(res, IntentClassificationResult)
    assert res.intent == UserIntent.REVISION
    assert "cheaper" in res.extracted_params["feedback"]


def test_classify_question_intent():
    query = "What is the best street food near Golden Temple in Amritsar?"
    res = TripRouter.classify_intent(query)

    assert isinstance(res, IntentClassificationResult)
    assert res.intent == UserIntent.QUESTION
    assert "Amritsar" in res.extracted_params["question"]


def test_classify_comparison_intent():
    query = "Compare Goa vs Pondicherry for a weekend beach getaway"
    res = TripRouter.classify_intent(query)

    assert isinstance(res, IntentClassificationResult)
    assert res.intent == UserIntent.COMPARISON
    assert "Goa" in res.extracted_params["cities"]
    assert "Pondicherry" in res.extracted_params["cities"]


def test_smart_request_api_routes_new_trip(client):
    res = client.post(
        "/api/smart-request",
        json={
            "text": "Plan a 3-day trip to Rishikesh under 10000",
            "origin": "Delhi",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "new_trip"
    assert data["routed_to"] == "/api/plan-trip"
    assert data["job_id"] is not None
    assert data["status"] == "pending"


def test_smart_request_api_routes_question(client):
    res = client.post(
        "/api/smart-request",
        json={
            "text": "Is it safe to visit Hampi during summer?",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "question"
    assert data["routed_to"] == "/api/ask-question"
    assert data["job_id"] is not None


def test_smart_request_api_routes_comparison(client):
    res = client.post(
        "/api/smart-request",
        json={
            "text": "Compare Manali vs Shimla for winter snow",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "comparison"
    assert data["routed_to"] == "/api/compare-trips"
    assert "Manali" in data["message"] or "Manali" in data["details"].get("cities", [])
