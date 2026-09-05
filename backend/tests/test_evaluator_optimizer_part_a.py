"""
Unit tests for Part A: Evaluator-Optimizer Pattern.
Verifies the Budget & Quality Evaluator agent logic:
- total_estimated_cost <= requested budget
- no generic "Miscellaneous" catch-all line items over 25% of a day's cost
- cost_breakdown items look specific and real, not vague filler
- multi-pass regeneration loop with feedback
"""

from unittest.mock import MagicMock

from trip_planner.crew import TripPlannerCrew
from trip_planner.schemas.models import EvaluationResult


def test_evaluator_passes_valid_itinerary():
    crew = TripPlannerCrew()
    valid_itinerary = {
        "destination_city": "Gokarna",
        "total_estimated_cost": 7500.0,
        "days": [
            {
                "day_number": 1,
                "estimated_cost": 3500.0,
                "cost_breakdown": [
                    {"item": "Zostel Gokarna Dorm Stay", "amount": 1200.0},
                    {"item": "Namaste Cafe Seafood Lunch", "amount": 800.0},
                    {"item": "Kudle Beach Sunset Drinks & Dinner", "amount": 1000.0},
                    {"item": "Local Auto to Om Beach", "amount": 500.0},
                ],
            },
            {
                "day_number": 2,
                "estimated_cost": 4000.0,
                "cost_breakdown": [
                    {"item": "Zostel Gokarna Dorm Stay", "amount": 1200.0},
                    {"item": "Beach Trek Guide & Refreshments", "amount": 1000.0},
                    {"item": "Chez Christophe French Dinner", "amount": 1200.0},
                    {"item": "Shared Auto Commute", "amount": 600.0},
                ],
            },
        ],
    }

    res = crew.evaluate_itinerary(valid_itinerary, target_budget=8000.0, destination_city="Gokarna")
    assert isinstance(res, EvaluationResult)
    assert res.passes is True
    assert "satisfies budget" in res.feedback.lower()


def test_evaluator_fails_real_overrun():
    crew = TripPlannerCrew()
    overrun_itinerary = {
        "destination_city": "Goa",
        "total_estimated_cost": 15000.0,
        "days": [
            {
                "day_number": 1,
                "estimated_cost": 8000.0,
                "cost_breakdown": [
                    {"item": "Taj Fort Aguada Stay", "amount": 5500.0},
                    {"item": "Fisherman's Wharf Dinner", "amount": 2500.0},
                ],
            },
            {
                "day_number": 2,
                "estimated_cost": 7000.0,
                "cost_breakdown": [
                    {"item": "Water Sports & Parasailing", "amount": 4000.0},
                    {"item": "Beach Shack Dining", "amount": 3000.0},
                ],
            },
        ],
    }

    # Requested budget is ₹8,000, but cost is ₹15,000
    res = crew.evaluate_itinerary(overrun_itinerary, target_budget=8000.0, destination_city="Goa")
    assert isinstance(res, EvaluationResult)
    assert res.passes is False
    assert "exceeds requested budget" in res.feedback.lower()
    assert "₹7,000" in res.feedback or "7000" in res.feedback
    assert "cut accommodation" in res.feedback.lower()


def test_evaluator_fails_fake_padding():
    crew = TripPlannerCrew()
    padded_itinerary = {
        "destination_city": "Rishikesh",
        "total_estimated_cost": 5000.0,
        "days": [
            {
                "day_number": 1,
                "estimated_cost": 5000.0,
                "cost_breakdown": [
                    {"item": "Zostel Rishikesh", "amount": 1000.0},
                    {"item": "Chotiwala Restaurant", "amount": 500.0},
                    {"item": "Miscellaneous Contingency Buffer", "amount": 2500.0},  # 50% of day's cost!
                    {"item": "Local Shared Auto", "amount": 1000.0},
                ],
            },
        ],
    }

    # Budget is 6000 (so cost 5000 is under budget), but has 50% Miscellaneous padding!
    res = crew.evaluate_itinerary(padded_itinerary, target_budget=6000.0, destination_city="Rishikesh")
    assert isinstance(res, EvaluationResult)
    assert res.passes is False
    assert "exceeding the 25% padding limit" in res.feedback.lower()
    assert "miscellaneous" in res.feedback.lower()


def test_evaluator_fails_vague_filler():
    crew = TripPlannerCrew()
    vague_itinerary = {
        "destination_city": "Shimla",
        "total_estimated_cost": 4000.0,
        "days": [
            {
                "day_number": 1,
                "estimated_cost": 4000.0,
                "cost_breakdown": [
                    {"item": "Hotel", "amount": 2000.0},  # Vague one-word filler
                    {"item": "Food", "amount": 1000.0},   # Vague one-word filler
                    {"item": "Transport", "amount": 1000.0},
                ],
            },
        ],
    }

    res = crew.evaluate_itinerary(vague_itinerary, target_budget=5000.0, destination_city="Shimla")
    assert isinstance(res, EvaluationResult)
    assert res.passes is False
    assert "vague line item" in res.feedback.lower()


def test_evaluator_optimizer_regeneration_loop_mocked(monkeypatch):
    """
    Verifies that run_with_evaluator_loop feeds feedback back to Concierge revision
    and succeeds when attempt 2 complies.
    """
    crew = TripPlannerCrew()

    attempt1_itinerary = {
        "destination_city": "Pondicherry",
        "total_estimated_cost": 12000.0,  # Over budget!
        "days": [{"day_number": 1, "estimated_cost": 12000.0, "cost_breakdown": [{"item": "Luxury Villa", "amount": 12000.0}]}],
    }

    attempt2_itinerary = {
        "destination_city": "Pondicherry",
        "total_estimated_cost": 4500.0,   # Fixed under budget!
        "days": [{"day_number": 1, "estimated_cost": 4500.0, "cost_breakdown": [{"item": "Promenade Beach Stay", "amount": 2500.0}, {"item": "Cafe des Arts Breakfast", "amount": 2000.0}]}],
    }

    mock_crew = MagicMock()
    mock_crew.kickoff.return_value = MagicMock(pydantic=None, raw=str(attempt1_itinerary).replace("'", '"'))
    monkeypatch.setattr(crew, "crew", lambda: mock_crew)

    mock_rev_crew = MagicMock()
    mock_rev_crew.kickoff.return_value = MagicMock(pydantic=None, raw=str(attempt2_itinerary).replace("'", '"'))
    monkeypatch.setattr(crew, "revision_crew", lambda: mock_rev_crew)

    inputs = {"destination_city": "Pondicherry", "budget": 5000.0}
    final_result = crew.run_with_evaluator_loop(inputs=inputs, max_retries=2)

    assert final_result["total_estimated_cost"] == 4500.0
    assert final_result["evaluation_passes"] is True
    assert final_result["evaluation_attempts"] == 2
