"""
Unit tests for Part D: Orchestrator-Workers Pattern.
Verifies:
- Subtask breakdown: day allocations, budget split, sequential transit link identification
- Concurrent worker execution: independent city day planning and accommodation selection
- Synthesizer: merging city deliverables into a cohesive whole-trip TripItinerary
- Single-city isolation: verifying that single-city trips strictly bypass the orchestrator
"""

from trip_planner.patterns.orchestrator import (
    DayPlanWorker,
    StayWorker,
    TransitWorker,
    TripOrchestrator,
    TripPlanOutline,
)
from trip_planner.schemas.models import TripItinerary


def test_orchestrator_subtask_breakdown():
    orchestrator = TripOrchestrator()
    inputs = {
        "origin": "Delhi",
        "cities": "Jaipur, Jodhpur, Udaipur",
        "trip_length": 6,
        "budget": 30000.0,
        "travelers": 2,
    }
    blueprint = orchestrator.breakdown_trip(inputs)

    assert isinstance(blueprint, TripPlanOutline)
    assert blueprint.origin_city == "Delhi"
    assert blueprint.destination_cities == ["Jaipur", "Jodhpur", "Udaipur"]
    assert blueprint.total_days == 6
    assert len(blueprint.city_allocations) == 3

    # 6 days distributed across 3 cities = 2 days per city
    for alloc in blueprint.city_allocations:
        assert alloc.allocated_days == 2
        assert alloc.allocated_budget == 10000.0


def test_worker_independence_and_concurrency():
    day_worker = DayPlanWorker()
    stay_worker = StayWorker()

    day = day_worker.plan_day(day_num=1, city="Jaipur", budget_for_day=5000.0)
    stay = stay_worker.select_stay(city="Jaipur", night_budget=2000.0, travelers=1)

    assert day.city == "Jaipur"
    assert day.estimated_cost == 5000.0
    assert len(day.cost_breakdown) == 4
    assert stay.city == "Jaipur"
    assert "Jaipur" in stay.name or "Residency" in stay.name


def test_orchestrator_synthesizes_whole_trip():
    orchestrator = TripOrchestrator()
    inputs = {
        "origin": "Delhi",
        "cities": "Delhi, Jaipur, Agra",
        "trip_length": 6,
        "budget": 30000.0,
        "travelers": 1,
        "currency": "INR",
    }
    itinerary = orchestrator.orchestrate_itinerary(inputs)

    assert isinstance(itinerary, TripItinerary)
    assert itinerary.origin_city == "Delhi"
    assert itinerary.destination_city == "Delhi"
    assert itinerary.cities_visited == ["Delhi", "Jaipur", "Agra"]
    assert itinerary.trip_length_days == 6
    assert len(itinerary.days) == 6

    # Verify continuous day numbering from 1 to 6
    for idx, day in enumerate(itinerary.days, start=1):
        assert day.day_number == idx

    # Verify sequential intercity transit route legs
    assert itinerary.intercity_transport is not None
    assert len(itinerary.intercity_transport.route_legs) == 3
    assert itinerary.intercity_transport.route_legs[0]["from_city"] == "Delhi"
    assert itinerary.intercity_transport.route_legs[0]["to_city"] == "Delhi"
    assert itinerary.intercity_transport.route_legs[1]["from_city"] == "Delhi"
    assert itinerary.intercity_transport.route_legs[1]["to_city"] == "Jaipur"
    assert itinerary.intercity_transport.route_legs[2]["from_city"] == "Jaipur"
    assert itinerary.intercity_transport.route_legs[2]["to_city"] == "Agra"

    # Verify stays across cities
    assert itinerary.recommended_stays is not None
    assert len(itinerary.recommended_stays) == 3

    # Verify orchestrator_used flag
    assert itinerary.orchestrator_used is True


def test_single_city_bypasses_orchestrator():
    single_city_input = {
        "origin": "Mumbai",
        "cities": "Goa",
        "trip_length": 3,
        "multi_city": False,
    }
    multi_city_input = {
        "origin": "Delhi",
        "cities": "Jaipur, Agra",
        "trip_length": 4,
        "multi_city": True,
    }

    assert TripOrchestrator.should_use_orchestrator(single_city_input) is False
    assert TripOrchestrator.should_use_orchestrator(multi_city_input) is True
