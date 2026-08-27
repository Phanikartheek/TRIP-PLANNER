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
