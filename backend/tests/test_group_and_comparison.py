"""
Unit tests for group cost splitting, trip comparison endpoint, and weather failure resilience.
"""

import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient
from trip_planner.api import db
from trip_planner.api.app import _execute_trip_job, app
from trip_planner.schemas.models import ItineraryDay, TripItinerary

client = TestClient(app)


def test_cost_per_person_reconciliation():
    """Verifies cost_per_person = total_estimated_cost / travelers calculation and rounding."""
    itinerary = TripItinerary(
        destination_city="Hyderabad",
        destination_country="India",
        trip_length_days=2,
        currency="INR",
        travelers=4,
        total_estimated_cost=20000.0,
        days=[
            ItineraryDay(
                day_number=1,
                theme="Fort & Charminar",
                morning="Visit Golconda Fort",
                afternoon="Lunch at Paradise Biryani",
                evening="Stroll near Charminar",
                estimated_cost=10000.0,
                cost_breakdown=[],
                weather_note="Clear skies - great outdoor day",
            ),
            ItineraryDay(
                day_number=2,
                theme="Museum & Lake",
                morning="Visit Salar Jung Museum",
                afternoon="Lunch at Shah Ghouse",
                evening="Boating at Hussain Sagar",
                estimated_cost=10000.0,
                cost_breakdown=[],
                weather_note="Rain likely (60%) - indoor plan recommended",
            ),
        ],
        packing_suggestions=["Cotton clothes"],
    )

    assert itinerary.travelers == 4
    assert itinerary.total_estimated_cost == 20000.0
    assert itinerary.cost_per_person == 5000.0


def test_cost_per_person_rounding():
    """Verifies correct 2-decimal rounding when total is not cleanly divisible."""
    itinerary = TripItinerary(
        destination_city="Warangal",
        destination_country="India",
        trip_length_days=1,
        currency="INR",
        travelers=3,
        total_estimated_cost=10000.0,
        days=[
            ItineraryDay(
                day_number=1,
                theme="Heritage",
                morning="Thousand Pillar Temple",
                afternoon="Warangal Fort",
                evening="Local market",
                estimated_cost=10000.0,
            )
        ],
        packing_suggestions=[],
    )

    assert itinerary.cost_per_person == 3333.33


def test_compare_trips_endpoint_validation():
    """Verifies POST /api/compare-trips input validation and rejection rules."""
    # 1. Invalid job_ids count (<2)
    resp = client.post("/api/compare-trips", json={"job_ids": ["job-1"]})
    assert resp.status_code == 400
    assert "between 2 and 3" in resp.json()["detail"]

    # 2. Non-existent job_id
    resp = client.post("/api/compare-trips", json={"job_ids": ["non-existent-1", "non-existent-2"]})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]

    # 3. Incomplete job
    db.init_db()
    db.create_job("incomplete-1", "plan", status="pending")
    db.create_job("incomplete-2", "plan", status="running")

    resp = client.post("/api/compare-trips", json={"job_ids": ["incomplete-1", "incomplete-2"]})
    assert resp.status_code == 400
    assert "not complete" in resp.json()["detail"]


def test_compare_trips_endpoint_success():
    """Verifies POST /api/compare-trips returning correct structural comparison for valid jobs."""
    db.init_db()

    job1_result = {
        "destination_city": "Visakhapatnam",
        "destination_country": "India",
        "trip_length_days": 3,
        "currency": "INR",
        "travelers": 2,
        "total_estimated_cost": 12000.0,
        "cost_per_person": 6000.0,
        "days": [
            {"day_number": 1, "weather_note": "Clear skies - pleasant weather"},
            {"day_number": 2, "weather_note": "Clear skies"},
            {"day_number": 3, "weather_note": "Rain likely (70%) - indoor museum plan"},
        ],
    }

    job2_result = {
        "destination_city": "Hyderabad",
        "destination_country": "India",
        "trip_length_days": 2,
        "currency": "INR",
        "travelers": 4,
        "total_estimated_cost": 20000.0,
        "cost_per_person": 5000.0,
        "days": [
            {"day_number": 1, "weather_note": "Clear skies"},
            {"day_number": 2, "weather_note": "Sunny"},
        ],
    }

    db.create_job("comp-job-1", "plan", status="pending")
    db.update_job("comp-job-1", status="complete", result=job1_result)

    db.create_job("comp-job-2", "plan", status="pending")
    db.update_job("comp-job-2", status="complete", result=job2_result)

    resp = client.post("/api/compare-trips", json={"job_ids": ["comp-job-1", "comp-job-2"]})
    assert resp.status_code == 200
    data = resp.json()

    assert "comparison" in data
    comp_list = data["comparison"]
    assert len(comp_list) == 2

    c1 = comp_list[0]
    assert c1["destination_city"] == "Visakhapatnam"
    assert c1["cost_per_person"] == 6000.0
    assert c1["travelers"] == 2
    assert "Rain likely on 1 of 3 days" in c1["weather_summary"]

    c2 = comp_list[1]
    assert c2["destination_city"] == "Hyderabad"
    assert c2["cost_per_person"] == 5000.0
    assert c2["travelers"] == 4
    assert c2["weather_summary"] == "Mostly clear / pleasant"


def test_compare_trips_weather_summary_threshold():
    """
    Unit test ensuring low rain probability (<=50%) with a weather_note mentioning 'rain'
    (e.g., 'Clear skies (22% rain)') is NOT counted as a rain day in weather_summary.
    """
    db.init_db()

    job1_result = {
        "destination_city": "Visakhapatnam",
        "destination_country": "India",
        "trip_length_days": 2,
        "currency": "INR",
        "travelers": 2,
        "total_estimated_cost": 12000.0,
        "days": [
            {"day_number": 1, "weather_note": "Rain likely (71%) - indoor museum plan"},
            {"day_number": 2, "weather_note": "Clear skies (22% rain) - ideal for outdoor beach walks"},
        ],
    }

    job2_result = {
        "destination_city": "Hyderabad",
        "destination_country": "India",
        "trip_length_days": 2,
        "currency": "INR",
        "travelers": 2,
        "total_estimated_cost": 10000.0,
        "days": [
            {"day_number": 1, "weather_note": "Clear skies", "rain_probability": 10},
            {"day_number": 2, "weather_note": "Sunny", "rain_probability": 15},
        ],
    }

    db.create_job("comp-threshold-1", "plan", status="pending")
    db.update_job("comp-threshold-1", status="complete", result=job1_result)

    db.create_job("comp-threshold-2", "plan", status="pending")
    db.update_job("comp-threshold-2", status="complete", result=job2_result)

    resp = client.post("/api/compare-trips", json={"job_ids": ["comp-threshold-1", "comp-threshold-2"]})
    assert resp.status_code == 200
    data = resp.json()

    comp_list = data["comparison"]
    c1 = comp_list[0]
    assert c1["destination_city"] == "Visakhapatnam"
    # Day 1 is 71% (>50%), Day 2 is 22% (<=50%) -> 1 of 2 days!
    assert c1["weather_summary"] == "Rain likely on 1 of 2 days"

    c2 = comp_list[1]
    assert c2["destination_city"] == "Hyderabad"
    assert c2["weather_summary"] == "Mostly clear / pleasant"


def test_trip_job_completes_when_weather_api_fails():
    """
    CRITICAL END-TO-END RESILIENCE TEST:
    Mocks get_forecast to throw an exception (simulating Open-Meteo downtime/404/timeout).
    Confirms that _execute_trip_job completes with status 'complete' without failing.
    """
    db.init_db()
    job_id = "test-weather-fail-job"
    db.create_job(job_id, "plan", status="pending")

    mock_crew_output = {
        "destination_city": "Kolkata",
        "destination_country": "India",
        "trip_length_days": 1,
        "currency": "INR",
        "travelers": 1,
        "total_estimated_cost": 3000.0,
        "days": [
            {
                "day_number": 1,
                "theme": "City of Joy",
                "morning": "Victoria Memorial",
                "afternoon": "Lunch at Arsalan Biryani",
                "evening": "Howrah Bridge walk",
                "estimated_cost": 3000.0,
                "cost_breakdown": [],
                "weather_note": "Weather data unavailable - standard seasonal precautions apply",
            }
        ],
        "packing_suggestions": [],
    }

    with patch("trip_planner.api.app.get_forecast", side_effect=Exception("Open-Meteo Server Error 503")):
        with patch("trip_planner.api.app._run_crew_sync", return_value=mock_crew_output):
            inputs = {
                "origin": "Delhi",
                "cities": "Kolkata",
                "interests": "culture",
                "trip_length": "1",
                "budget": "₹3,000 INR",
                "currency": "INR",
                "travelers": "1",
                "language": "en",
            }
            asyncio.run(_execute_trip_job(job_id, inputs))

    job_rec = db.get_job(job_id)
    assert job_rec["status"] == "complete"
    assert job_rec["result"]["destination_city"] == "Kolkata"
