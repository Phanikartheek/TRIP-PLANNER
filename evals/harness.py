"""
Agent Evaluation & Benchmark Harness for AI Trip Planner.

Evaluates LLM and Multi-Agent outputs against objective quality gates:
1. Budget Compliance Score (0-100)
2. Landmark-to-City Grounding Score (0-100, zero cross-city hallucinations)
3. Temporal Completeness Score (0-100)
4. Logistics & Transit Score (0-100)
5. Composite Overall Quality Score (0-100)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


KNOWN_LANDMARK_MAP = {
    "undavalli": "vijayawada",
    "kanaka durga": "vijayawada",
    "prakasam barrage": "vijayawada",
    "bhavani island": "vijayawada",
    "mypadu beach": "nellore",
    "nelapattu": "nellore",
    "pulicat": "nellore",
    "baga beach": "goa",
    "calangute": "goa",
    "fort aguada": "goa",
    "anテクノ beach": "goa",
    "city palace": "udaipur",
    "lake pichola": "udaipur",
    "hadimba": "manali",
    "solang valley": "manali",
    "rohtang": "manali"
}


class BenchmarkHarness:
    """Automated evaluation harness for trip itineraries."""

    @staticmethod
    def evaluate_itinerary(
        itinerary: dict[str, Any],
        requested_budget: float | None = None,
        expected_city: str | None = None
    ) -> dict[str, Any]:
        """Evaluates a single itinerary output and returns metric scores."""
        scores = {}

        # 1. Budget Compliance Score
        total_cost = float(itinerary.get("total_estimated_cost") or 0.0)
        target_budget = float(requested_budget or total_cost or 25000.0)

        if target_budget <= 0:
            scores["budget_compliance"] = 100.0
        elif total_cost <= target_budget * 1.05:
            scores["budget_compliance"] = 100.0
        else:
            overrun_pct = ((total_cost - target_budget) / target_budget) * 100.0
            # Deduct 2 points per 1% overrun, minimum 0
            scores["budget_compliance"] = max(0.0, round(100.0 - (overrun_pct * 2.0), 1))

        # 2. Landmark Grounding Score
        grounding_violations = 0
        total_landmarks_checked = 0

        city_target = (expected_city or str(itinerary.get("destination_city", ""))).lower().strip()
        days = itinerary.get("days", [])
        if isinstance(days, list):
            for day in days:
                if not isinstance(day, dict):
                    continue
                day_city = str(day.get("city") or city_target).lower()
                activities = day.get("activities", [])
                for act in activities:
                    if isinstance(act, dict):
                        act_text = (str(act.get("title", "")) + " " + str(act.get("description", ""))).lower()
                        for landmark, true_city in KNOWN_LANDMARK_MAP.items():
                            if landmark in act_text:
                                total_landmarks_checked += 1
                                # If landmark is associated with a specific city, check it doesn't contradict day_city
                                if true_city not in day_city and day_city not in true_city:
                                    grounding_violations += 1

        if total_landmarks_checked == 0 or grounding_violations == 0:
            scores["landmark_grounding"] = 100.0
        else:
            scores["landmark_grounding"] = max(0.0, round(100.0 - ((grounding_violations / total_landmarks_checked) * 100.0), 1))

        # 3. Temporal Completeness Score
        complete_days = 0
        total_days = len(days) if isinstance(days, list) else 0

        if total_days > 0:
            for day in days:
                if isinstance(day, dict):
                    acts = day.get("activities", [])
                    has_morning = any("morning" in str(a.get("time_of_day", "")).lower() or "am" in str(a.get("time", "")).lower() for a in acts if isinstance(a, dict))
                    has_afternoon = any("afternoon" in str(a.get("time_of_day", "")).lower() or "pm" in str(a.get("time", "")).lower() for a in acts if isinstance(a, dict))
                    has_evening = any("evening" in str(a.get("time_of_day", "")).lower() or "pm" in str(a.get("time", "")).lower() for a in acts if isinstance(a, dict))
                    if len(acts) >= 3 or (has_morning and (has_afternoon or has_evening)):
                        complete_days += 1
            scores["temporal_completeness"] = round((complete_days / total_days) * 100.0, 1)
        else:
            scores["temporal_completeness"] = 0.0

        # 4. Logistics Score
        logistics_points = 0
        if itinerary.get("accommodation_recommendations"):
            logistics_points += 40
        if itinerary.get("packing_suggestions"):
            logistics_points += 30
        if itinerary.get("daily_budget_breakdown") or total_cost > 0:
            logistics_points += 30
        scores["logistics_integrity"] = float(logistics_points)

        # 5. Composite Overall Quality Score
        composite = (
            (scores["budget_compliance"] * 0.30) +
            (scores["landmark_grounding"] * 0.30) +
            (scores["temporal_completeness"] * 0.25) +
            (scores["logistics_integrity"] * 0.15)
        )
        scores["overall_quality_score"] = round(composite, 1)
        scores["passed"] = bool(scores["overall_quality_score"] >= 80.0)

        return scores

    @classmethod
    def run_benchmark_suite(cls, output_file: str | Path | None = None) -> dict[str, Any]:
        """Runs the standard test battery and saves benchmark_report.json."""
        # Standard benchmark scenarios
        test_cases = [
            {
                "name": "Benchmark 1: Budget Goa Vacation",
                "requested_budget": 20000.0,
                "expected_city": "Goa",
                "itinerary": {
                    "destination_city": "Goa",
                    "total_estimated_cost": 19500.0,
                    "days": [
                        {
                            "day_number": 1,
                            "city": "North Goa",
                            "activities": [
                                {"title": "Calangute Morning Walk", "time_of_day": "morning"},
                                {"title": "Baga Beach Water Sports", "time_of_day": "afternoon"},
                                {"title": "Fort Aguada Sunset", "time_of_day": "evening"}
                            ]
                        }
                    ],
                    "accommodation_recommendations": [{"name": "Seaside Hostel"}],
                    "packing_suggestions": ["Sunscreen", "Swimwear"],
                    "daily_budget_breakdown": [{"day": 1, "cost": 3000}]
                }
            },
            {
                "name": "Benchmark 2: Multi-City Andhra Grounding Check",
                "requested_budget": 30000.0,
                "expected_city": "Vijayawada",
                "itinerary": {
                    "destination_city": "Vijayawada",
                    "total_estimated_cost": 28000.0,
                    "days": [
                        {
                            "day_number": 1,
                            "city": "Vijayawada",
                            "activities": [
                                {"title": "Undavalli Caves Exploration", "time_of_day": "morning"},
                                {"title": "Kanaka Durga Temple Darshan", "time_of_day": "afternoon"},
                                {"title": "Prakasam Barrage Walk", "time_of_day": "evening"}
                            ]
                        },
                        {
                            "day_number": 2,
                            "city": "Nellore",
                            "activities": [
                                {"title": "Mypadu Beach Visit", "time_of_day": "morning"},
                                {"title": "Nelapattu Bird Sanctuary", "time_of_day": "afternoon"},
                                {"title": "Local Seafood Dinner", "time_of_day": "evening"}
                            ]
                        }
                    ],
                    "accommodation_recommendations": [{"name": "Grand Vijayawada"}],
                    "packing_suggestions": ["Cotton clothes"],
                    "daily_budget_breakdown": [{"day": 1, "cost": 4000}]
                }
            }
        ]

        results = []
        for tc in test_cases:
            res = cls.evaluate_itinerary(
                tc["itinerary"],
                requested_budget=tc.get("requested_budget"),
                expected_city=tc.get("expected_city")
            )
            results.append({
                "test_case": tc["name"],
                "metrics": res,
                "passed": res["passed"]
            })

        avg_score = round(sum(r["metrics"]["overall_quality_score"] for r in results) / len(results), 1)
        all_passed = all(r["passed"] for r in results)

        report = {
            "harness_version": "1.0.0",
            "total_cases": len(results),
            "passed_cases": sum(1 for r in results if r["passed"]),
            "average_overall_score": avg_score,
            "status": "PASSED" if all_passed else "FAILED",
            "results": results
        }

        if output_file:
            out_path = Path(output_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)

        return report


if __name__ == "__main__":
    report_path = Path(__file__).resolve().parent / "benchmark_report.json"
    rep = BenchmarkHarness.run_benchmark_suite(output_file=report_path)
    print("\n=======================================================")
    print("      AGENT EVALUATION & BENCHMARK HARNESS")
    print("=======================================================")
    print(f"Status: {rep['status']}")
    print(f"Score:  {rep['average_overall_score']}/100.0")
    print(f"Passed: {rep['passed_cases']}/{rep['total_cases']}")
    print(f"Saved:  {report_path}")
    print("=======================================================\n")
