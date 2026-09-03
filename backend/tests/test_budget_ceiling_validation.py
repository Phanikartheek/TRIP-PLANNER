"""
Unit tests for deterministic budget ceiling validation and warning generation.
"""

from unittest.mock import MagicMock, patch

from trip_planner.api.app import _run_crew_sync


def test_budget_exceeded_warning_populated_when_over_budget():
    """Verify that an itinerary exceeding requested budget by >5% gets an honest warning without altering numbers."""
    inputs = {
        "origin": "Bengaluru",
        "cities": "Gokarna",
        "interests": "beaches, temples",
        "trip_length": 3,
        "budget": 25000,
        "currency": "INR",
        "travelers": 1,
    }

    mock_pydantic_res = MagicMock()
    mock_pydantic_res.model_dump.return_value = {
        "destination_city": "Gokarna",
        "destination_country": "India",
        "trip_length_days": 3,
        "currency": "INR",
        "total_estimated_cost": 34300.0,
        "days": [
            {
                "day_number": 1,
                "theme": "Arrival & Beach Walk",
                "morning": "Reach Gokarna",
                "afternoon": "Om Beach",
                "evening": "Sunset",
                "night": "Dinner",
                "estimated_cost": 11400.0,
                "cost_breakdown": [
                    {"item": "Hotel Stay", "amount": 7500.0},
                    {"item": "Food & Cabs", "amount": 3900.0},
                ],
            }
        ],
        "packing_suggestions": ["Sunscreen"],
    }

    mock_crew_result = MagicMock()
    mock_crew_result.pydantic = mock_pydantic_res

    with patch("crewai.Crew.kickoff", return_value=mock_crew_result):
        res = _run_crew_sync(inputs)

    # Asserts that numbers were NOT modified or scaled
    assert res["total_estimated_cost"] == 34300.0
    assert res["days"][0]["cost_breakdown"][0]["amount"] == 7500.0

    # Asserts warning field is correctly populated
    assert res["budget_exceeded_warning"] is not None
    assert "₹34,300" in res["budget_exceeded_warning"]
    assert "₹25,000" in res["budget_exceeded_warning"]
    assert "₹9,300" in res["budget_exceeded_warning"]
    assert "37.2%" in res["budget_exceeded_warning"]
    assert res["budget_alert"] == res["budget_exceeded_warning"]


def test_no_budget_warning_when_within_budget():
    """Verify that an itinerary within budget receives no warning and numbers remain unmodified."""
    inputs = {
        "origin": "Delhi",
        "cities": "Shimla",
        "interests": "mountains",
        "trip_length": 3,
        "budget": 25000,
        "currency": "INR",
        "travelers": 1,
    }

    mock_pydantic_res = MagicMock()
    mock_pydantic_res.model_dump.return_value = {
        "destination_city": "Shimla",
        "destination_country": "India",
        "trip_length_days": 3,
        "currency": "INR",
        "total_estimated_cost": 22000.0,
        "days": [
            {
                "day_number": 1,
                "theme": "Mall Road",
                "morning": "Arrival",
                "afternoon": "Mall Road Walk",
                "evening": "Cafe",
                "night": "Dinner",
                "estimated_cost": 7333.33,
                "cost_breakdown": [{"item": "Hotel", "amount": 4000.0}],
            }
        ],
        "packing_suggestions": ["Jacket"],
    }

    mock_crew_result = MagicMock()
    mock_crew_result.pydantic = mock_pydantic_res

    with patch("crewai.Crew.kickoff", return_value=mock_crew_result):
        res = _run_crew_sync(inputs)

    assert res["total_estimated_cost"] == 22000.0
    assert res["budget_exceeded_warning"] is None
    assert res["budget_alert"] is None


def test_budget_warning_with_custom_currency():
    """Verify currency formatting (USD $) in budget overrun warning."""
    inputs = {
        "origin": "Bengaluru",
        "cities": "Bali",
        "interests": "beaches",
        "trip_length": 5,
        "budget": 1000,
        "currency": "USD",
        "travelers": 1,
    }

    mock_pydantic_res = MagicMock()
    mock_pydantic_res.model_dump.return_value = {
        "destination_city": "Bali",
        "destination_country": "Indonesia",
        "trip_length_days": 5,
        "currency": "USD",
        "total_estimated_cost": 1400.0,
        "days": [],
        "packing_suggestions": ["Swimwear"],
    }

    mock_crew_result = MagicMock()
    mock_crew_result.pydantic = mock_pydantic_res

    with patch("crewai.Crew.kickoff", return_value=mock_crew_result):
        res = _run_crew_sync(inputs)

    assert res["total_estimated_cost"] == 1400.0
    assert res["budget_exceeded_warning"] is not None
    assert "$1,400" in res["budget_exceeded_warning"]
    assert "$1,000" in res["budget_exceeded_warning"]
    assert "$400" in res["budget_exceeded_warning"]
    assert "40.0%" in res["budget_exceeded_warning"]
