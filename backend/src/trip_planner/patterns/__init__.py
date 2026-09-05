"""
Agentic Workflow Patterns for AI Trip Planner:
1. Routing (TripRouter, UserIntent, IntentClassificationResult, RouteDecision, TripTopology, TravelerPersona)
2. Parallelization (ParallelResearcher, ConsolidatedResearch)
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

__all__ = [
    "UserIntent",
    "IntentClassificationResult",
    "TripTopology",
    "TravelerPersona",
    "RouteDecision",
    "TripRouter",
    "ConsolidatedResearch",
    "ParallelResearcher",
]
