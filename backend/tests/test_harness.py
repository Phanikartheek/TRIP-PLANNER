import pytest
from pathlib import Path
from evals.harness import BenchmarkHarness


def test_harness_scores_perfect_itinerary():
    """
    Verifies that a well-grounded, within-budget itinerary achieves 100/100 score.
    """
    perfect_trip = {
        "destination_city": "Goa",
        "total_estimated_cost": 15000.0,
        "days": [
            {
                "day_number": 1,
                "city": "Goa",
                "activities": [
                    {"title": "Baga Beach stroll", "time_of_day": "morning"},
                    {"title": "Calangute lunch", "time_of_day": "afternoon"},
                    {"title": "Fort Aguada sunset", "time_of_day": "evening"}
                ]
            }
        ],
        "accommodation_recommendations": [{"name": "Beach Villa"}],
        "packing_suggestions": ["Swimwear"],
        "daily_budget_breakdown": [{"day": 1, "cost": 3000}]
    }

    metrics = BenchmarkHarness.evaluate_itinerary(perfect_trip, requested_budget=15000.0, expected_city="Goa")
    assert metrics["budget_compliance"] == 100.0
    assert metrics["landmark_grounding"] == 100.0
    assert metrics["temporal_completeness"] == 100.0
    assert metrics["overall_quality_score"] == 100.0
    assert metrics["passed"] is True


def test_harness_penalizes_budget_overrun():
    """
    Verifies that an itinerary exceeding budget by 20% has its budget_compliance score docked.
    """
    over_budget_trip = {
        "destination_city": "Manali",
        "total_estimated_cost": 24000.0,  # 20% over 20,000
        "days": [
            {
                "day_number": 1,
                "city": "Manali",
                "activities": [
                    {"title": "Hadimba Temple", "time_of_day": "morning"},
                    {"title": "Solang Valley", "time_of_day": "afternoon"},
                    {"title": "Mall Road", "time_of_day": "evening"}
                ]
            }
        ],
        "accommodation_recommendations": [{"name": "Snow Hotel"}],
        "packing_suggestions": ["Jacket"],
        "daily_budget_breakdown": [{"day": 1, "cost": 6000}]
    }

    metrics = BenchmarkHarness.evaluate_itinerary(over_budget_trip, requested_budget=20000.0, expected_city="Manali")
    # 20% overrun * 2.0 = 40 point deduction -> 60.0
    assert metrics["budget_compliance"] == 60.0
    assert metrics["overall_quality_score"] < 100.0


def test_harness_penalizes_cross_city_hallucinations():
    """
    Verifies that assigning Undavalli Caves (Vijayawada) to Nellore docks the grounding score.
    """
    hallucinated_trip = {
        "destination_city": "Nellore",
        "total_estimated_cost": 10000.0,
        "days": [
            {
                "day_number": 1,
                "city": "Nellore",
                "activities": [
                    {"title": "Visit Undavalli Caves", "time_of_day": "morning"},  # Undavalli is Vijayawada!
                    {"title": "Nelapattu Bird Sanctuary", "time_of_day": "afternoon"}
                ]
            }
        ],
        "accommodation_recommendations": [{"name": "Nellore Lodge"}],
        "packing_suggestions": ["Cap"],
        "daily_budget_breakdown": [{"day": 1, "cost": 2000}]
    }

    metrics = BenchmarkHarness.evaluate_itinerary(hallucinated_trip, requested_budget=10000.0, expected_city="Nellore")
    assert metrics["landmark_grounding"] < 100.0


def test_harness_run_benchmark_suite(tmp_path: Path):
    """
    Verifies that BenchmarkHarness.run_benchmark_suite runs and exports report JSON.
    """
    report_file = tmp_path / "benchmark_report.json"
    rep = BenchmarkHarness.run_benchmark_suite(output_file=report_file)
    assert rep["status"] == "PASSED"
    assert rep["total_cases"] >= 2
    assert report_file.exists()
