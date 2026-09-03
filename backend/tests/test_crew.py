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
        CitySelection()  # missing required city field


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
    from trip_planner.api import db
    from trip_planner.api.app import app

    client = TestClient(app)

    # 1. Non-existent job_id -> 404
    res_404 = client.post("/api/revise-trip", json={"job_id": "non-existent-uuid", "feedback": "Make it cheaper"})
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()

    # 2. Pending job_id -> 400
    db.create_job(job_id="pending-job-uuid", job_type="plan", status="pending")
    res_400 = client.post("/api/revise-trip", json={"job_id": "pending-job-uuid", "feedback": "Make it cheaper"})
    assert res_400.status_code == 400
    assert "not completed" in res_400.json()["detail"].lower()


def test_qa_crew_uses_only_local_qa_expert(crew_instance):
    """Confirm the Q&A crew is single-agent and uses only local_qa_expert."""
    crew = crew_instance.qa_crew()
    assert len(crew.agents) == 1
    assert crew.agents[0].role == "Local Q&A Expert"
    assert len(crew.tasks) == 1
    assert crew.tasks[0].agent.role == "Local Q&A Expert"


def test_destination_question_schema_validation():
    """Confirm DestinationQuestion accepts valid payload and rejects missing fields."""
    from trip_planner.schemas.models import DestinationQuestion

    req = DestinationQuestion(job_id="test-job-uuid", question="Where is the best biryani?")
    assert req.job_id == "test-job-uuid"
    assert req.question == "Where is the best biryani?"

    with pytest.raises(ValueError):
        DestinationQuestion(job_id="only-job-id")  # missing question


def test_qa_response_schema_validation_with_grounding_claims():
    """Confirm QAResponse schema correctly accepts grounded_claims and ungrounded_claims as separate lists."""
    from trip_planner.schemas.models import QAExchange, QAResponse

    # 1. Valid fully-grounded response
    qa_resp = QAResponse(
        answer="Try Naidu Gari Kunda Biryani on MG Road.",
        grounded_claims=["Naidu Gari Kunda Biryani on MG Road"],
        ungrounded_claims=[],
        sources=["https://example.com/biryani"],
    )
    assert qa_resp.answer == "Try Naidu Gari Kunda Biryani on MG Road."
    assert qa_resp.grounded_claims == ["Naidu Gari Kunda Biryani on MG Road"]
    assert qa_resp.ungrounded_claims == []
    assert qa_resp.sources == ["https://example.com/biryani"]

    # 2. Mixed response with ungrounded claims
    qa_mixed = QAResponse(
        answer="PVP Square has cinemas. Typically malls are less crowded on weekday mornings.",
        grounded_claims=["PVP Square has cinemas"],
        ungrounded_claims=["malls are less crowded on weekday mornings"],
    )
    assert len(qa_mixed.grounded_claims) == 1
    assert len(qa_mixed.ungrounded_claims) == 1

    # 3. QAExchange model test
    exchange = QAExchange(
        question="Where is good biryani?",
        answer="Naidu Gari Kunda Biryani",
        grounded_claims=["Naidu Gari Kunda Biryani"],
        ungrounded_claims=[],
    )
    assert exchange.question == "Where is good biryani?"
    assert exchange.answer == "Naidu Gari Kunda Biryani"
    assert exchange.timestamp > 0


def test_ask_question_multi_turn_history_passed_to_context():
    """Confirm conversation history from Turn 1 is passed into Turn 2's context."""
    from unittest.mock import patch

    from fastapi.testclient import TestClient
    from trip_planner.api import db
    from trip_planner.api.app import app

    client = TestClient(app)
    root_job_id = "test-session-root-job"

    # Setup initial completed trip job with qa_history in DB
    db.create_job(root_job_id, job_type="plan", status="complete")
    db.update_job(
        root_job_id,
        result={"destination_city": "Vijayawada", "city": "Vijayawada"},
        qa_history=[
            {
                "question": "Where can I find good biryani here?",
                "answer": "Naidu Gari Kunda Biryani and Sai Silver Dum Biryani are top choices.",
                "grounded_claims": ["Naidu Gari Kunda Biryani", "Sai Silver Dum Biryani"],
                "ungrounded_claims": [],
                "timestamp": 1700000000.0,
            }
        ],
    )

    with patch("trip_planner.api.app._execute_qa_job"):
        # Submit second turn question
        res = client.post(
            "/api/ask-question",
            json={"job_id": root_job_id, "question": "Is there anything cheaper than that nearby?"},
        )
    assert res.status_code == 200
    new_qa_job_id = res.json()["job_id"]

    # Verify created job in DB
    created_job = db.get_job(new_qa_job_id)
    assert created_job is not None
    assert created_job["status"] in ("pending", "running", "failed")
    assert created_job["parent_job_id"] == root_job_id


def test_ask_question_endpoint_rejects_invalid_or_incomplete_job():
    """Confirm POST /api/ask-question with non-existent or incomplete job_id returns 404/400."""
    from fastapi.testclient import TestClient
    from trip_planner.api import db
    from trip_planner.api.app import app

    client = TestClient(app)

    # 1. Non-existent job_id -> 404
    res_404 = client.post("/api/ask-question", json={"job_id": "non-existent-uuid", "question": "Where is good biryani?"})
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()

    # 2. Pending job_id -> 400
    db.create_job("pending-job-uuid-qa", job_type="plan", status="pending")
    res_400 = client.post("/api/ask-question", json={"job_id": "pending-job-uuid-qa", "question": "Where is good biryani?"})
    assert res_400.status_code == 400
    assert "not completed" in res_400.json()["detail"].lower()



