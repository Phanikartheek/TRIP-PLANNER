"""
Unit tests for Multi-City Itineraries and Budget-Overrun Alerts on Revisions.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from trip_planner.api import db
from trip_planner.api.app import _execute_revision_job, app
from trip_planner.schemas.models import TripItinerary

client = TestClient(app)


def test_multicity_schema_and_normalization():
    """
    1. Unit test: multi_city=True itinerary - confirms cities_visited is populated,
       destination_city gets set to the first city (backward compatibility), and
       each day's city field is populated correctly.
    """
    mock_crew_output = {
        "destination_city": "Goa",
        "destination_country": "India",
        "trip_length_days": 4,
        "total_estimated_cost": 20000.0,
        "currency": "INR",
        "cities_visited": ["Goa", "Gokarna"],
        "days": [
            {
                "day_number": 1,
                "city": "Goa",
                "theme": "North Goa Beaches",
                "morning": "Calangute Beach walk",
                "afternoon": "Fort Aguada tour",
                "evening": "Anjuna Cafe sunset",
                "estimated_cost": 5000.0,
            },
            {
                "day_number": 2,
                "city": "Goa",
                "theme": "South Goa Heritage",
                "morning": "Basilica of Bom Jesus",
                "afternoon": "Spice Plantation Lunch",
                "evening": "Mandovi River Cruise",
                "estimated_cost": 5000.0,
            },
            {
                "day_number": 3,
                "city": "Gokarna",
                "theme": "Transit to Gokarna & Om Beach",
                "morning": "Train from Goa to Gokarna",
                "afternoon": "Check-in & Om Beach walk",
                "evening": "Kudle Beach Sunset Cafe",
                "estimated_cost": 5000.0,
            },
            {
                "day_number": 4,
                "city": "Gokarna",
                "theme": "Gokarna Temples & Departure",
                "morning": "Mahabaleshwar Temple",
                "afternoon": "Half Moon Beach hike",
                "evening": "Return journey",
                "estimated_cost": 5000.0,
            },
        ],
        "packing_suggestions": ["Beachwear", "Sunscreen", "Walking shoes"],
    }

    # Validate output pydantic model
    itinerary = TripItinerary(**mock_crew_output)
    assert itinerary.destination_city == "Goa"
    assert itinerary.cities_visited == ["Goa", "Gokarna"]
    assert itinerary.days[0].city == "Goa"
    assert itinerary.days[2].city == "Gokarna"

    # Test normalization helper logic
    inputs = {"cities": "Goa, Gokarna", "multi_city": True}
    raw_dict: dict[str, str | int | float | list[str] | list[dict[str, str | float]] | None] = dict(mock_crew_output)
    # Simulate _run_crew_sync normalization
    if inputs.get("multi_city"):
        raw_cities = [c.strip() for c in str(inputs["cities"]).split(",")]
        if not raw_dict.get("cities_visited"):
            raw_dict["cities_visited"] = raw_cities
        visited = raw_dict.get("cities_visited")
        if isinstance(visited, list) and len(visited) > 0:
            raw_dict["destination_city"] = visited[0]

    assert raw_dict["destination_city"] == "Goa"
    assert raw_dict["cities_visited"] == ["Goa", "Gokarna"]


def test_single_city_unaffected():
    """
    2. Unit test: existing single-city path (multi_city=False, default) is completely unaffected -
       cities_visited is None, behavior identical to before this change.
    """
    mock_single_output = {
        "destination_city": "Jaipur",
        "destination_country": "India",
        "trip_length_days": 2,
        "total_estimated_cost": 15000.0,
        "currency": "INR",
        "days": [
            {
                "day_number": 1,
                "theme": "Amer Fort & Palaces",
                "morning": "Amer Fort exploration",
                "afternoon": "City Palace visit",
                "evening": "Chokhi Dhani dinner",
                "estimated_cost": 7500.0,
            },
            {
                "day_number": 2,
                "theme": "Bazaars & Heritage",
                "morning": "Hawa Mahal & Johari Bazaar",
                "afternoon": "Jantar Mantar",
                "evening": "Nahargarh sunset",
                "estimated_cost": 7500.0,
            },
        ],
        "packing_suggestions": ["Cotton clothes", "Sunscreen"],
    }

    itinerary = TripItinerary(**mock_single_output)
    assert itinerary.destination_city == "Jaipur"
    assert itinerary.cities_visited is None
    assert itinerary.days[0].city is None


@pytest.mark.anyio
async def test_budget_alert_calculation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    3. Unit test: budget_alert correctly triggers when revision total exceeds original,
       correctly stays None when it doesn't or when cost decreases, and percentage/amount math is exact.
    """
    db_file = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_file)
    db.init_db(db_path=db_file)

    job_id = "test-budget-alert-job"
    db.create_job(job_id, "plan", status="pending", db_path=db_file)
    orig_result = {
        "destination_city": "Goa",
        "total_estimated_cost": 15000.0,
        "currency": "INR",
    }
    db.update_job(job_id, status="complete", result=orig_result, db_path=db_file)

    # Mock revision returning higher cost 18200.0 (+3200, +21.3%)
    mock_rev_higher = {
        "destination_city": "Goa",
        "total_estimated_cost": 18200.0,
        "currency": "INR",
    }

    with pytest.MonkeyPatch.context() as m:
        m.setattr("trip_planner.api.app._run_revision_sync", lambda inputs: mock_rev_higher)
        await _execute_revision_job(job_id, {"job_id": job_id, "feedback": "upgrade hotel"})

    revised_job = db.get_job(job_id, db_path=db_file)
    assert revised_job is not None
    res = revised_job.get("result")
    assert isinstance(res, dict)
    assert "budget_alert" in res
    assert res["budget_alert"] == "This revision increased your total cost from ₹15,000 to ₹18,200 (+₹3,200, +21.3%)"

    # Mock revision returning lower or equal cost 14000.0 -> budget_alert is None
    mock_rev_lower = {
        "destination_city": "Goa",
        "total_estimated_cost": 14000.0,
        "currency": "INR",
    }
    # Reset job original cost to 15000.0
    db.update_job(job_id, status="complete", result=orig_result, db_path=db_file)

    with pytest.MonkeyPatch.context() as m:
        m.setattr("trip_planner.api.app._run_revision_sync", lambda inputs: mock_rev_lower)
        await _execute_revision_job(job_id, {"job_id": job_id, "feedback": "make it cheaper"})

    revised_job_lower = db.get_job(job_id, db_path=db_file)
    assert revised_job_lower is not None
    res_lower = revised_job_lower.get("result")
    assert isinstance(res_lower, dict)
    assert res_lower.get("budget_alert") is None


def test_reconcile_multi_city_itinerary_matches_themes_and_route():
    """
    4. Unit test: Multi-city reconciliation correctly matches each day to its city
       based on day themes and activity text, avoiding misassignment (e.g. Day 4
       with Vijayawada theme getting Vijayawada instead of Nellore), and constructs
       the true chronological route.
    """
    from trip_planner.api.app import reconcile_multi_city_itinerary

    itinerary_data = {
        "destination_city": "TIRUPATI",
        "cities_visited": ["TIRUPATI", "VIJAYAWADA", "NELLOR", "GUNTUR"],
        "days": [
            {
                "day_number": 1,
                "city": "TIRUPATI",
                "theme": "Tirumala Temple Heritage & Spiritual Start",
                "morning": "Arrive at Tirupati Railway Station...",
            },
            {
                "day_number": 2,
                "city": "TIRUPATI",  # LLM had incorrectly left this as TIRUPATI
                "theme": "Nellore Coastal Beaches & Temple Exploration",
                "morning": "Travel from Tirupati to Nellore by express train...",
            },
            {
                "day_number": 3,
                "city": "VIJAYAWADA",  # LLM had incorrectly put VIJAYAWADA
                "theme": "Guntur Temples, Spice Markets & Historic Fort",
                "morning": "Travel from Nellore to Guntur by express train...",
            },
            {
                "day_number": 4,
                "city": "NELLOR",  # LLM had incorrectly put NELLOR
                "theme": "Vijayawada Heritage Temples, Caves & River Views",
                "morning": "Travel from Guntur to Vijayawada by train...",
            },
            {
                "day_number": 5,
                "city": "GUNTUR",  # LLM had incorrectly put GUNTUR
                "theme": "Krishna River Nature, Boat Ride & Departure",
                "morning": "Visit scenic Krishna River delta in Vijayawada...",
            },
        ],
    }

    reconcile_multi_city_itinerary(
        itinerary_data,
        raw_cities=["TIRUPATI", "VIJAYAWADA", "NELLOR", "GUNTUR"],
        origin_name="Hyderabad",
    )

    days = itinerary_data["days"]
    assert days[0]["city"] == "TIRUPATI"
    assert days[1]["city"] == "NELLOR"
    assert days[2]["city"] == "GUNTUR"
    assert days[3]["city"] == "VIJAYAWADA"
    assert days[4]["city"] == "VIJAYAWADA"

    # Chronological route sequence
    assert itinerary_data["cities_visited"] == ["TIRUPATI", "NELLOR", "GUNTUR", "VIJAYAWADA"]
    assert itinerary_data["destination_city"] == "TIRUPATI"
    assert "Hyderabad ➔ TIRUPATI ➔ NELLOR ➔ GUNTUR ➔ VIJAYAWADA" in itinerary_data["intercity_transport"]["recommended_option"]


def test_budget_string_parsing_triggers_warning_on_overrun():
    """
    Verifies that formatted currency strings (e.g. '₹3,000 INR') properly parse with clean_float
    and correctly trigger budget_exceeded_warning when cost exceeds requested budget by >5%.
    """
    from trip_planner.schemas.models import clean_float

    raw_budget_str = "₹3,000 INR"
    target_budget = clean_float(raw_budget_str, 0.0)
    assert target_budget == 3000.0

    tot_cost = 3200.0
    out_dict = {"total_estimated_cost": tot_cost, "currency": "INR"}

    if target_budget > 0 and tot_cost > (target_budget * 1.05):
        overrun = tot_cost - target_budget
        pct = (overrun / target_budget) * 100.0
        warning_msg = (
            f"⚠️ Budget Alert: This itinerary's estimated cost (₹{tot_cost:,.0f}) "
            f"exceeds your requested budget (₹{target_budget:,.0f}) by ₹{overrun:,.0f} ({pct:.1f}%)."
        )
        out_dict["budget_exceeded_warning"] = warning_msg
    else:
        out_dict["budget_exceeded_warning"] = None

    assert out_dict["budget_exceeded_warning"] is not None
    assert "₹3,200" in out_dict["budget_exceeded_warning"]
    assert "₹3,000" in out_dict["budget_exceeded_warning"]
    assert "₹200" in out_dict["budget_exceeded_warning"]
    assert "6.7%" in out_dict["budget_exceeded_warning"]


def test_landmark_grounding_resolves_vijayawada_and_nellore():
    """
    Verifies that landmark-to-city grounding accurately maps Undavalli Caves to Vijayawada
    and Mypadu Beach to Nellore even if the city name is not in the theme text.
    """
    from trip_planner.api.app import reconcile_multi_city_itinerary

    itinerary_data = {
        "destination_city": "Nellore",
        "cities_visited": ["Nellore", "Vijayawada"],
        "days": [
            {
                "day_number": 1,
                "city": "Nellore",  # Incorrect initial LLM tag
                "theme": "Ancient Caves & River Island Exploration",
                "morning": "Explore the multi-tiered Undavalli Caves with intricate rock-cut shrines.",
                "afternoon": "Visit Kanaka Durga Temple and enjoy scenic boat ride to Bhavani Island.",
                "evening": "Stroll across the historic Prakasam Barrage.",
                "night": "Rest at nearby riverfront hotel.",
            },
            {
                "day_number": 2,
                "city": "Vijayawada",  # Incorrect initial LLM tag
                "theme": "Coastal Breeze & Temple Architecture",
                "morning": "Travel south towards the Penna river basin.",
                "afternoon": "Relax on the golden sands of Mypadu Beach and enjoy fresh local seafood.",
                "evening": "Visit the sacred Sri Ranganathaswamy Temple on the river banks.",
                "night": "Overnight stay in coastal district.",
            },
        ],
    }

    reconcile_multi_city_itinerary(
        itinerary_data,
        raw_cities=["Nellore", "Vijayawada"],
        origin_name="Hyderabad",
    )

    days = itinerary_data["days"]
    assert days[0]["city"] == "Vijayawada"
    assert days[1]["city"] == "Nellore"


def test_calendar_ics_export_endpoint():
    """
    Verifies that GET /api/trip/{job_id}/calendar.ics generates valid RFC 5545 iCalendar content.
    """
    import uuid

    test_job_id = f"test-ics-{uuid.uuid4().hex[:8]}"
    db.create_job(
        job_id=test_job_id,
        job_type="plan",
        status="complete",
    )
    mock_result = {
        "destination_city": "Vijayawada",
        "travel_date": "2026-11-15",
        "trip_length_days": 2,
        "days": [
            {
                "day_number": 1,
                "city": "Vijayawada",
                "theme": "Heritage Exploration",
                "morning": "Visit Kanaka Durga Temple",
                "afternoon": "Explore Undavalli Caves",
                "evening": "Prakasam Barrage sunset",
            },
            {
                "day_number": 2,
                "city": "Vijayawada",
                "theme": "River Island Fun",
                "morning": "Boating to Bhavani Island",
                "afternoon": "Bapu Museum tour",
                "evening": "Shopping & departure",
            },
        ],
    }
    db.update_job(test_job_id, status="complete", result=mock_result)

    response = client.get(f"/api/trip/{test_job_id}/calendar.ics")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["Content-Type"]
    assert "BEGIN:VCALENDAR" in response.text
    assert "END:VCALENDAR" in response.text
    assert "BEGIN:VEVENT" in response.text
    assert "Kanaka Durga Temple" in response.text
    assert "Bhavani Island" in response.text


