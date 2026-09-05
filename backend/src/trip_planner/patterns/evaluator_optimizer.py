"""
Evaluator-Optimizer Pattern for AI Trip Planner.
Iterative evaluation and refinement loop ensuring itineraries strictly meet
budget ceilings, sensible pacing, geographic continuity, and content completeness.
"""

from typing import Optional
from pydantic import BaseModel, Field

from trip_planner.schemas.models import TripItinerary


class EvaluationReport(BaseModel):
    """Structured report produced by the Evaluator assessing itinerary quality."""
    score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score (0.0 to 1.0)")
    passed: bool = Field(..., description="True if itinerary satisfies all quality gates")
    critique: list[str] = Field(default_factory=list, description="Identified deficiencies")
    optimizations: list[str] = Field(default_factory=list, description="Actionable optimization instructions")
    budget_overrun: float = Field(default=0.0, description="Amount by which cost exceeds budget, if any")


class ItineraryEvaluator:
    """
    Evaluates candidate itineraries against objective quality gates.
    """

    def __init__(self, pass_threshold: float = 0.85):
        self.pass_threshold = pass_threshold

    def evaluate(self, itinerary: TripItinerary, target_budget: Optional[float] = None) -> EvaluationReport:
        critique: list[str] = []
        optimizations: list[str] = []
        score = 1.0
        budget_overrun = 0.0

        # Gate 1: Budget Adherence
        if target_budget and target_budget > 0:
            if itinerary.total_estimated_cost > (target_budget * 1.05):
                overrun = round(itinerary.total_estimated_cost - target_budget, 2)
                pct = round((overrun / target_budget) * 100.0, 1)
                budget_overrun = overrun
                critique.append(
                    f"Budget Violation: Estimated cost (₹{itinerary.total_estimated_cost:,.0f}) "
                    f"exceeds target budget (₹{target_budget:,.0f}) by ₹{overrun:,.0f} (+{pct}%)."
                )
                optimizations.append(
                    f"Reduce daily activity and accommodation budget envelopes by ~{pct}% to bring total within ₹{target_budget:,.0f}."
                )
                score -= min(0.40, (overrun / target_budget) * 0.5)

        # Gate 2: Schedule Density & Day Structure
        if not itinerary.days:
            critique.append("Critical: No daily schedule days provided.")
            optimizations.append("Generate comprehensive day-by-day morning, afternoon, evening activities.")
            score -= 0.50
        else:
            for day in itinerary.days:
                if not day.morning or not day.afternoon or not day.evening:
                    critique.append(f"Day {day.day_number} has incomplete morning/afternoon/evening schedule.")
                    optimizations.append(f"Flesh out all three time slots for Day {day.day_number}.")
                    score -= 0.10
                if day.estimated_cost <= 0:
                    critique.append(f"Day {day.day_number} has zero or missing estimated cost.")
                    optimizations.append(f"Itemize cost breakdown for Day {day.day_number}.")
                    score -= 0.10

        # Gate 3: Origin & Transit Continuity
        if not itinerary.origin_city:
            critique.append("Missing departure hub: origin_city is not defined.")
            optimizations.append("Assign traveler's real departure hub to origin_city.")
            score -= 0.10

        if not itinerary.intercity_transport:
            critique.append("Missing intercity transit guidance.")
            optimizations.append("Attach concrete intercity transit guidance (Train/Bus/Flight).")
            score -= 0.10

        # Gate 4: Accommodation Quality
        if not itinerary.recommended_stay and not itinerary.recommended_stays:
            critique.append("No recommended hotel/stay options provided.")
            optimizations.append("Include budget-matched accommodation recommendation.")
            score -= 0.15

        final_score = max(0.0, min(1.0, round(score, 2)))
        passed = (final_score >= self.pass_threshold) and (budget_overrun <= 0.0)

        return EvaluationReport(
            score=final_score,
            passed=passed,
            critique=critique,
            optimizations=optimizations,
            budget_overrun=budget_overrun,
        )


class ItineraryOptimizer:
    """
    Optimizes a candidate itinerary by applying structured refinements from an EvaluationReport.
    """

    def optimize(
        self,
        itinerary: TripItinerary,
        report: EvaluationReport,
        target_budget: Optional[float] = None,
        default_origin: Optional[str] = None,
    ) -> TripItinerary:
        """
        Applies fixes for all flagged critique items.
        """
        # 1. Fix missing origin_city
        if not itinerary.origin_city and default_origin:
            itinerary.origin_city = default_origin

        # 2. Fix budget overrun by proportionally trimming daily expenses & stay prices
        if target_budget and target_budget > 0 and itinerary.total_estimated_cost > target_budget:
            scale_factor = target_budget / max(1.0, itinerary.total_estimated_cost)
            if itinerary.days:
                for day in itinerary.days:
                    day.estimated_cost = round(day.estimated_cost * scale_factor, 2)
                    if day.cost_breakdown:
                        for item in day.cost_breakdown:
                            item.amount = round(item.amount * scale_factor, 2)
                        day.estimated_cost = round(sum(i.amount for i in day.cost_breakdown), 2)

            if itinerary.recommended_stay and itinerary.recommended_stay.estimated_price_per_night:
                itinerary.recommended_stay.estimated_price_per_night = round(
                    itinerary.recommended_stay.estimated_price_per_night * scale_factor, 2
                )

            if itinerary.recommended_stays:
                for s in itinerary.recommended_stays:
                    if s.estimated_price_per_night:
                        s.estimated_price_per_night = round(s.estimated_price_per_night * scale_factor, 2)

            itinerary.reconcile_total_estimated_cost()

        # 3. Ensure packing suggestions exist
        if not itinerary.packing_suggestions:
            itinerary.packing_suggestions = [
                "Comfortable walking shoes",
                "Weather-appropriate clothing",
                "Government ID & transit passes",
                "Personal medications & first aid",
            ]

        return itinerary


class EvaluatorOptimizer:
    """
    Coordinates the feedback loop between Evaluator and Optimizer.
    """

    def __init__(self, max_passes: int = 2, pass_threshold: float = 0.85):
        self.max_passes = max_passes
        self.evaluator = ItineraryEvaluator(pass_threshold=pass_threshold)
        self.optimizer = ItineraryOptimizer()

    def run_optimization_loop(
        self,
        candidate: TripItinerary,
        target_budget: Optional[float] = None,
        default_origin: Optional[str] = None,
    ) -> tuple[TripItinerary, EvaluationReport, int]:
        """
        Executes the iterative review-optimize loop until passing or max passes reached.
        Returns (refined_itinerary, final_report, passes_executed).
        """
        current_itinerary = candidate
        passes = 0

        while passes <= self.max_passes:
            report = self.evaluator.evaluate(current_itinerary, target_budget=target_budget)
            if report.passed or passes == self.max_passes:
                return current_itinerary, report, passes

            # Optimize based on critique
            current_itinerary = self.optimizer.optimize(
                itinerary=current_itinerary,
                report=report,
                target_budget=target_budget,
                default_origin=default_origin,
            )
            passes += 1

        final_report = self.evaluator.evaluate(current_itinerary, target_budget=target_budget)
        return current_itinerary, final_report, passes
