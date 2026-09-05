"""
Four Agentic Workflow Patterns for AI Trip Planner:
1. Routing (TripRouter, UserIntent, IntentClassificationResult, RouteDecision, TripTopology, TravelerPersona)
2. Parallelization (ParallelResearcher, ConsolidatedResearch)
3. Orchestrator-Workers (TripOrchestrator, DayPlanWorker, StayWorker, TransitWorker, TripPlanOutline, TripSubtask)
4. Evaluator-Optimizer (EvaluatorOptimizer, ItineraryEvaluator, ItineraryOptimizer, EvaluationReport)
"""

from trip_planner.patterns.router import (
    IntentClassificationResult,
    RouteDecision,
    TravelerPersona,
    TripRouter,
    TripTopology,
    UserIntent,
)
from trip_planner.patterns.parallelizer import (
    ConsolidatedResearch,
    ParallelResearcher,
)
from trip_planner.patterns.orchestrator import (
    DayPlanWorker,
    StayWorker,
    TransitWorker,
    TripOrchestrator,
    TripPlanOutline,
    TripSubtask,
)
from trip_planner.patterns.evaluator_optimizer import (
    EvaluationReport,
    EvaluatorOptimizer,
    ItineraryEvaluator,
    ItineraryOptimizer,
)

__all__ = [
    "UserIntent",
    "IntentClassificationResult",
    "TripTopology",
    "TravelerPersona",
    "RouteDecision",
    "TripRouter",
    "ConsolidatedResearch",
    "ParallelResearcher",
    "DayPlanWorker",
    "StayWorker",
    "TransitWorker",
    "TripOrchestrator",
    "TripPlanOutline",
    "TripSubtask",
    "EvaluationReport",
    "ItineraryEvaluator",
    "ItineraryOptimizer",
    "EvaluatorOptimizer",
]
