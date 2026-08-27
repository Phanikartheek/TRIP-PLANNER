"""
Tests focus on wiring correctness, not LLM output quality — you can't
unit-test "did the agent pick a good city" deterministically, so we test
what's actually testable: does the crew assemble the right agents/tasks,
are tools attached where expected, do schemas validate correctly.
"""

import os

import pytest

os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")

from trip_planner.crew import TripPlannerCrew  # noqa: E402
from trip_planner.schemas.models import CitySelection, TripItinerary  # noqa: E402


@pytest.fixture
def crew_instance():
    return TripPlannerCrew()


def test_crew_has_three_agents_in_order(crew_instance):
    crew = crew_instance.crew()
    roles = [a.role for a in crew.agents]
    assert roles == [
        "City Selection Expert",
        "Local Tour Guide",
        "Amazing Travel Concierge",
    ]


def test_crew_has_three_tasks_assigned_correctly(crew_instance):
    crew = crew_instance.crew()
    assert len(crew.tasks) == 3
    assert crew.tasks[0].agent.role == "City Selection Expert"
    assert crew.tasks[1].agent.role == "Local Tour Guide"
    assert crew.tasks[2].agent.role == "Amazing Travel Concierge"


def test_final_task_depends_on_prior_two(crew_instance):
    crew = crew_instance.crew()
    final_task = crew.tasks[2]
    context_descriptions = {t.description for t in final_task.context}
    assert crew.tasks[0].description in context_descriptions
    assert crew.tasks[1].description in context_descriptions


def test_search_tool_attached_to_city_selector_and_local_expert(crew_instance):
    crew = crew_instance.crew()
    for agent in crew.agents[:2]:
        tool_names = {t.name for t in agent.tools}
        assert "web_search" in tool_names


def test_scrape_tool_only_attached_to_local_expert(crew_instance):
    crew = crew_instance.crew()
    city_selector_tools = {t.name for t in crew.agents[0].tools}
    local_expert_tools = {t.name for t in crew.agents[1].tools}
    assert "Read website content" not in city_selector_tools
    assert "Read website content" in local_expert_tools


def test_city_selection_schema_rejects_missing_fields():
    with pytest.raises(ValueError):
        CitySelection(city="Lisbon")  # missing required fields


def test_trip_itinerary_schema_accepts_valid_payload():
    itinerary = TripItinerary(
        destination_city="Lisbon",
        destination_country="Portugal",
        trip_length_days=1,
        total_estimated_cost=150.0,
        days=[
            {
                "day_number": 1,
                "theme": "Old Town",
                "morning": "Walk Alfama",
                "afternoon": "Belem Tower",
                "evening": "Fado dinner",
                "estimated_cost": 150.0,
            }
        ],
        packing_suggestions=["comfortable shoes", "light jacket"],
    )
    assert itinerary.trip_length_days == 1
    assert len(itinerary.days) == 1
    assert itinerary.total_estimated_cost == 150.0


def test_trip_itinerary_reconciles_total_estimated_cost_with_days_sum():
    itinerary = TripItinerary(
        destination_city="Munnar",
        destination_country="India",
        trip_length_days=2,
        total_estimated_cost=9999.0,  # Mismatched initial value
        days=[
            {
                "day_number": 1,
                "theme": "Arrival",
                "morning": "Flight",
                "afternoon": "Tea museum",
                "evening": "Dinner",
                "estimated_cost": 5000.0,
            },
            {
                "day_number": 2,
                "theme": "Peaks",
                "morning": "Trek",
                "afternoon": "Dam",
                "evening": "Viewpoint",
                "estimated_cost": 3500.0,
            },
        ],
        packing_suggestions=["jacket"],
    )
    # The validator automatically recomputed total to 8500.0 (5000 + 3500)
    assert itinerary.total_estimated_cost == 8500.0


def test_revision_crew_uses_only_travel_concierge(crew_instance):
    """Confirm the revision crew is single-agent and uses only travel_concierge."""
    crew = crew_instance.revision_crew()
    assert len(crew.agents) == 1
    assert crew.agents[0].role == "Amazing Travel Concierge"
    assert len(crew.tasks) == 1
    assert crew.tasks[0].agent.role == "Amazing Travel Concierge"
    assert crew.tasks[0].output_pydantic == TripItinerary


def test_revision_request_schema_validation():
    """Confirm RevisionRequest accepts valid payload and rejects missing fields."""
    from trip_planner.schemas.models import RevisionRequest

    req = RevisionRequest(job_id="test-job-uuid", feedback="Replace Day 2 trek with beach walk")
    assert req.job_id == "test-job-uuid"
    assert req.feedback == "Replace Day 2 trek with beach walk"

    with pytest.raises(ValueError):
        RevisionRequest(job_id="only-job-id")  # missing feedback


def test_revise_trip_endpoint_rejects_invalid_or_incomplete_job():
    """Confirm POST /api/revise-trip with non-existent or incomplete job_id returns 404/400."""
    from fastapi.testclient import TestClient
    from trip_planner.api.app import JOB_STORE, app

    client = TestClient(app)

    # 1. Non-existent job_id -> 404
    res_404 = client.post("/api/revise-trip", json={"job_id": "non-existent-uuid", "feedback": "Make it cheaper"})
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()

    # 2. Pending job_id -> 400
    JOB_STORE["pending-job-uuid"] = {"job_id": "pending-job-uuid", "status": "pending", "result": None}
    res_400 = client.post("/api/revise-trip", json={"job_id": "pending-job-uuid", "feedback": "Make it cheaper"})
    assert res_400.status_code == 400
    assert "not completed" in res_400.json()["detail"].lower()

