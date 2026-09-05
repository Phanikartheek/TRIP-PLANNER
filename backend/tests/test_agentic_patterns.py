"""
Unit tests for the Four Agentic Workflow Patterns:
1. Routing Pattern (TripRouter)
2. Parallelization Pattern (ParallelResearcher)
3. Orchestrator-Workers Pattern (TripOrchestrator)
4. Evaluator-Optimizer Pattern (EvaluatorOptimizer)
"""

import pytest
from trip_planner.patterns import (
    ConsolidatedResearch,
    DayPlanWorker,
    EvaluationReport,
    EvaluatorOptimizer,
    ItineraryEvaluator,
    ItineraryOptimizer,
    ParallelResearcher,
    StayWorker,
    TransitWorker,
    TravelerPersona,
    TripOrchestrator,
    TripRouter,
    TripTopology,
)
from trip_planner.schemas.models import (
    AccommodationOption,
    CostItem,
    ItineraryDay,
    TripItinerary,
)


# ==========================================
# 1. ROUTING PATTERN TESTS
# ==========================================

def test_router_single_city_weekend():
    inputs = {
        "cities": "Goa",
        "trip_length": 2,
        "budget": 8000.0,
        "interests": "beach relax",
        "travelers": 1,
    }
    decision = TripRouter.classify(inputs)
    assert decision.topology == TripTopology.WEEKEND_GETAWAY
    assert decision.persona in [TravelerPersona.FAMILY_LEISURE, TravelerPersona.BUDGET_BACKPACKER]
    assert len(decision.budget_guardrail) > 0


def test_router_multi_city_expedition():
    inputs = {
        "cities": "Delhi, Jaipur, Agra",
        "trip_length": 8,
        "budget": 60000.0,
        "multi_city": True,
        "interests": "heritage monuments fort palaces",
        "travelers": 2,
    }
    decision = TripRouter.classify(inputs)
    assert decision.topology == TripTopology.MULTI_CITY
    assert decision.persona == TravelerPersona.HERITAGE_CULTURE
    assert "UNESCO" in decision.recommended_focus[0] or "Historical" in decision.recommended_focus[0]
    assert any("backtracking" in c.lower() for c in decision.special_cautions)


def test_router_budget_backpacker():
    inputs = {
        "cities": "Rishikesh",
        "trip_length": 4,
        "budget": 4000.0,
        "interests": "hostel, cheap food, backpacking",
        "travelers": 1,
    }
    decision = TripRouter.classify(inputs)
    assert decision.persona == TravelerPersona.BUDGET_BACKPACKER
    assert "Hostels & Budget Stays" in decision.recommended_focus
    assert "stays" in decision.budget_guardrail


def test_router_luxury_comfort():
    inputs = {
        "cities": "Udaipur",
        "trip_length": 3,
        "budget": 80000.0,
        "interests": "luxury 5 star palace stay fine dining spa",
        "travelers": 2,
    }
    decision = TripRouter.classify(inputs)
    assert decision.persona == TravelerPersona.LUXURY_COMFORT
    assert "Premium 4/5-star Hotels & Resorts" in decision.recommended_focus


# ==========================================
# 2. PARALLELIZATION PATTERN TESTS
# ==========================================

def test_parallel_researcher_concurrent_execution():
    call_log = []

    def mock_search(query: str) -> str:
        call_log.append(query)
        if "weather" in query:
            return "Sunny and pleasant, 25°C average."
        if "travel from" in query:
            return "Vande Bharat Express train links origin to destination in 4.5 hours."
        if "local food" in query:
            return "Iconic local Biryani\nFamous Pootharekulu sweet\nSouth Indian filter coffee"
        if "attractions" in query:
            return "Kanaka Durga Temple\nPrakasam Barrage\nUndavalli Caves"
        return "Budget hotels near railway station with great reviews."

    researcher = ParallelResearcher(max_workers=4, search_fn=mock_search)
    res = researcher.run_parallel_research(
        origin="Bengaluru",
        destination="Vijayawada",
        interests="culture food",
        budget=20000.0,
        travel_date="2026-10-15",
    )

    assert isinstance(res, ConsolidatedResearch)
    assert res.destination == "Vijayawada"
    assert res.origin == "Bengaluru"
    assert "Sunny and pleasant" in res.weather_summary
    assert "Vande Bharat" in res.transit_summary
    assert len(res.cuisine_highlights) >= 2
    assert len(res.attractions_highlights) >= 2
    assert len(call_log) == 5  # All 5 tasks executed concurrently


# ==========================================
# 3. ORCHESTRATOR-WORKERS PATTERN TESTS
# ==========================================

def test_orchestrator_subtask_breakdown():
    orchestrator = TripOrchestrator()
    inputs = {
        "origin": "Mumbai",
        "cities": "Jaipur, Jodhpur, Udaipur",
        "trip_length": 6,
        "budget": 30000.0,
        "travelers": 2,
    }
    blueprint = orchestrator.breakdown_trip(inputs)
    assert blueprint.origin_city == "Mumbai"
    assert len(blueprint.destination_cities) == 3
    assert blueprint.total_days == 6
    assert len(blueprint.city_allocations) == 3
    # 6 days distributed across 3 cities = 2 days each
    assert all(alloc.allocated_days == 2 for alloc in blueprint.city_allocations)
    assert sum(alloc.allocated_budget for alloc in blueprint.city_allocations) == 30000.0


def test_orchestrator_synthesizes_itinerary():
    orchestrator = TripOrchestrator()
    inputs = {
        "origin": "Delhi",
        "cities": "Rishikesh",
        "trip_length": 3,
        "budget": 15000.0,
        "travelers": 1,
    }
    itinerary = orchestrator.orchestrate_itinerary(inputs)
    assert isinstance(itinerary, TripItinerary)
    assert itinerary.origin_city == "Delhi"
    assert itinerary.destination_city == "Rishikesh"
    assert len(itinerary.days) == 3
    assert itinerary.total_estimated_cost == 15000.0
    assert itinerary.recommended_stay is not None
    assert itinerary.intercity_transport is not None
    assert len(itinerary.packing_suggestions) >= 3


# ==========================================
# 4. EVALUATOR-OPTIMIZER PATTERN TESTS
# ==========================================

def test_evaluator_flags_budget_overrun():
    evaluator = ItineraryEvaluator()
    itinerary = TripItinerary(
        destination_city="Goa",
        origin_city="Mumbai",
        destination_country="India",
        trip_length_days=2,
        total_estimated_cost=25000.0,
        days=[
            ItineraryDay(
                day_number=1,
                city="Goa",
                theme="Beach",
                morning="Calangute",
                afternoon="Baga",
                evening="Anjuna sunset",
                estimated_cost=15000.0,
                cost_breakdown=[CostItem(item="Luxury Stay", amount=15000.0)],
            ),
            ItineraryDay(
                day_number=2,
                city="Goa",
                theme="Heritage",
                morning="Old Goa churches",
                afternoon="Panaji Latin quarter",
                evening="Cruise",
                estimated_cost=10000.0,
                cost_breakdown=[CostItem(item="Dinner & Cruise", amount=10000.0)],
            ),
        ],
        packing_suggestions=["swimwear", "sunscreen"],
        recommended_stay=AccommodationOption(
            name="Taj Exotica",
            city="Goa",
            category="5-star",
            address_or_area="Benaulim",
            estimated_price_per_night=15000.0,
            why_recommended="Luxury beach resort",
        ),
    )

    # Requested budget is 15000, but cost is 25000
    report = evaluator.evaluate(itinerary, target_budget=15000.0)
    assert report.passed is False
    assert report.budget_overrun == 10000.0
    assert any("Budget Violation" in c for c in report.critique)
    assert len(report.optimizations) > 0


def test_evaluator_optimizer_refinement_loop():
    loop = EvaluatorOptimizer(max_passes=2)
    itinerary = TripItinerary(
        destination_city="Manali",
        origin_city=None,  # Missing origin
        destination_country="India",
        trip_length_days=2,
        total_estimated_cost=20000.0,
        days=[
            ItineraryDay(
                day_number=1,
                city="Manali",
                theme="Arrival",
                morning="Mall Road",
                afternoon="Hadimba Temple",
                evening="Cafes",
                estimated_cost=10000.0,
                cost_breakdown=[CostItem(item="Resort", amount=10000.0)],
            ),
            ItineraryDay(
                day_number=2,
                city="Manali",
                theme="Solang Valley",
                morning="Paragliding",
                afternoon="Snow point",
                evening="Old Manali dinner",
                estimated_cost=10000.0,
                cost_breakdown=[CostItem(item="Activities", amount=10000.0)],
            ),
        ],
        packing_suggestions=[],
        recommended_stay=AccommodationOption(
            name="Solang Valley Resort",
            city="Manali",
            category="Luxury",
            address_or_area="Solang",
            estimated_price_per_night=8000.0,
            why_recommended="Scenic mountain views",
        ),
    )

    # Target budget is 12000.0, default origin is Chandigarh
    refined, final_report, passes = loop.run_optimization_loop(
        candidate=itinerary,
        target_budget=12000.0,
        default_origin="Chandigarh",
    )

    assert refined.origin_city == "Chandigarh"
    assert refined.total_estimated_cost <= 12000.0
    assert len(refined.packing_suggestions) >= 3
    assert passes >= 1
    assert final_report.budget_overrun <= 0.0


# ==========================================
# 5. INTEGRATION TEST: TRIP PLANNER CREW
# ==========================================

def test_crew_run_agentic_workflow():
    from trip_planner.crew import TripPlannerCrew

    crew = TripPlannerCrew()
    inputs = {
        "origin": "Mumbai",
        "cities": "Gokarna",
        "trip_length": 3,
        "budget": 12000.0,
        "interests": "beach trek, sunset cafes",
        "travelers": 1,
    }

    result = crew.run_agentic_workflow(inputs)
    assert isinstance(result, dict)
    assert result["origin_city"] == "Mumbai"
    assert result["destination_city"] == "Gokarna"
    assert result["total_estimated_cost"] <= 12000.0
    assert "route_decision" in result
    assert "evaluation_report" in result
    assert result["evaluation_report"]["passed"] is True
