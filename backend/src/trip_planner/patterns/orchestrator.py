"""
Orchestrator-Workers Pattern for AI Trip Planner.
A central Orchestrator dynamically breaks down complex trip requirements
into discrete subtasks, dispatches them to specialized worker agents,
and synthesizes their individual deliverables into a unified TripItinerary.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field

from trip_planner.schemas.models import (
    AccommodationOption,
    CostItem,
    IntercityTransport,
    ItineraryDay,
    TripItinerary,
)


class TripSubtask(BaseModel):
    """Subtask created by the Orchestrator for a specialized worker."""
    task_type: str  # 'day_plan', 'stay', 'transit', 'checklist'
    target_city: str
    allocated_days: int = 1
    allocated_budget: float = 0.0
    context: dict[str, Any] = Field(default_factory=dict)


class TripPlanOutline(BaseModel):
    """High-level execution blueprint broken down by the Orchestrator."""
    destination_cities: list[str]
    origin_city: str
    total_days: int
    total_budget: float
    travelers: int
    city_allocations: list[TripSubtask] = Field(default_factory=list)


class DayPlanWorker:
    """Worker responsible for planning morning, afternoon, evening activities and cost breakdowns."""

    def plan_day(self, day_num: int, city: str, budget_for_day: float, theme: str = "Sightseeing") -> ItineraryDay:
        cost_stay = round(budget_for_day * 0.40, 2)
        cost_food = round(budget_for_day * 0.30, 2)
        cost_activities = round(budget_for_day * 0.20, 2)
        cost_transit = round(budget_for_day * 0.10, 2)

        breakdown = [
            CostItem(item="Hotel Stay / Accommodation", amount=cost_stay),
            CostItem(item="Regional Breakfast, Lunch & Dinner", amount=cost_food),
            CostItem(item="Attraction Entry & Activities", amount=cost_activities),
            CostItem(item="Local Auto / Cab Commute", amount=cost_transit),
        ]

        return ItineraryDay(
            day_number=day_num,
            city=city,
            theme=f"{city} Exploration & Culture",
            morning=f"Visit prime landmark and heritage sights in {city}.",
            afternoon=f"Explore vibrant local markets, artisan stores, and savor famous regional dishes.",
            evening=f"Scenic evening walk, cultural sunset viewpoint, and relaxing dinner.",
            estimated_cost=round(budget_for_day, 2),
            cost_breakdown=breakdown,
            weather_note=f"Pleasant conditions in {city}, ideal for sightseeing.",
        )


class StayWorker:
    """Worker responsible for selecting accommodations matching destination and budget."""

    def select_stay(self, city: str, night_budget: float, travelers: int = 1) -> AccommodationOption:
        tier = "Budget" if night_budget < 1500 else ("Comfort / Mid-range" if night_budget < 4000 else "Luxury")
        hotel_name = f"Hotel {city} Residency"
        return AccommodationOption(
            name=hotel_name,
            city=city,
            category=f"{tier} Hotel",
            address_or_area=f"Central Town, near Railway/Transit Hub, {city}",
            estimated_price_per_night=round(night_budget, 2),
            why_recommended=f"Centrally located, highly rated {tier.lower()} stay matching your budget envelope.",
        )


class TransitWorker:
    """Worker responsible for intercity transit and sequential connection routing."""

    def plan_transit(self, origin: str, cities: list[str], total_transit_budget: float) -> IntercityTransport:
        if len(cities) <= 1:
            dest = cities[0] if cities else origin
            return IntercityTransport(
                mode="Express Train / Flight",
                recommended_option=f"Direct Express Transit ({origin} to {dest})",
                estimated_cost_per_person=round(total_transit_budget, 2),
                travel_duration="3 - 6 hrs",
                why_recommended=f"Convenient and direct connection from departure hub {origin} to {dest}.",
                local_connect_tips="Prepaid cabs and autos readily available outside the transit terminal.",
                route_legs=[],
            )

        # Multi-leg transit
        legs: list[dict[str, Any]] = []
        all_stops = [origin] + cities
        leg_cost = round(total_transit_budget / max(1, len(all_stops) - 1), 2)

        for i in range(len(all_stops) - 1):
            f_city = all_stops[i]
            t_city = all_stops[i + 1]
            legs.append(
                {
                    "from_city": f_city,
                    "to_city": t_city,
                    "mode": "Express Train / Volvo Bus",
                    "recommended_option": f"Intercity Express ({f_city} ➔ {t_city})",
                    "estimated_cost_per_person": leg_cost,
                    "travel_duration": "3 - 4 hrs",
                    "why_recommended": f"Optimal sequential corridor link between {f_city} and {t_city}.",
                    "local_connect_tips": "Station-front auto stands and local taxi services.",
                }
            )

        return IntercityTransport(
            mode="Multi-Leg Rail / Road Transit",
            recommended_option=f"Multi-City Corridor ({' ➔ '.join(all_stops)})",
            estimated_cost_per_person=round(total_transit_budget, 2),
            travel_duration="Sequential Corridor",
            why_recommended="Sequential route minimizing travel fatigue and backtracking.",
            local_connect_tips="Local connectivity at every stop.",
            route_legs=legs,
        )


class TripOrchestrator:
    """
    Central Orchestrator breaking down trip goals, delegating to specialized workers,
    and synthesizing results into a unified TripItinerary.
    """

    def __init__(
        self,
        day_worker: Optional[DayPlanWorker] = None,
        stay_worker: Optional[StayWorker] = None,
        transit_worker: Optional[TransitWorker] = None,
    ):
        self.day_worker = day_worker or DayPlanWorker()
        self.stay_worker = stay_worker or StayWorker()
        self.transit_worker = transit_worker or TransitWorker()

    def breakdown_trip(self, inputs: dict[str, Any]) -> TripPlanOutline:
        """
        Analyzes high-level parameters and creates a structured execution blueprint.
        """
        origin = str(inputs.get("origin", "Origin")).strip()
        cities_raw = str(inputs.get("cities", inputs.get("destination_city", "Vijayawada"))).strip()
        city_list = [c.strip() for c in cities_raw.split(",") if c.strip()]
        if not city_list:
            city_list = ["Vijayawada"]

        total_days = max(1, int(inputs.get("trip_length", inputs.get("days", 3))))
        total_budget = float(inputs.get("budget", 25000.0))
        travelers = max(1, int(inputs.get("travelers", 1)))

        # Allocate days across cities
        base_days_per_city = max(1, total_days // len(city_list))
        remaining_days = total_days % len(city_list)

        allocations: list[TripSubtask] = []
        for idx, city in enumerate(city_list):
            d_count = base_days_per_city + (1 if idx < remaining_days else 0)
            city_budget = (total_budget / total_days) * d_count
            allocations.append(
                TripSubtask(
                    task_type="city_bundle",
                    target_city=city,
                    allocated_days=d_count,
                    allocated_budget=city_budget,
                    context={"origin": origin, "travelers": travelers},
                )
            )

        return TripPlanOutline(
            destination_cities=city_list,
            origin_city=origin,
            total_days=total_days,
            total_budget=total_budget,
            travelers=travelers,
            city_allocations=allocations,
        )

    @classmethod
    def should_use_orchestrator(cls, inputs: dict[str, Any]) -> bool:
        """
        Determines whether the Orchestrator-Workers pattern should execute.
        Only multi-city trips use this pattern; single-city trips bypass it completely.
        """
        cities_raw = str(inputs.get("cities", "")).strip()
        city_list = [c.strip() for c in cities_raw.split(",") if c.strip()]
        is_multi = bool(inputs.get("multi_city"))
        return len(city_list) > 1 or (is_multi and len(city_list) > 1)

    def _plan_city_worker(self, subtask: TripSubtask, daily_budget: float) -> dict[str, Any]:
        """
        Concurrent worker planning that city's portion (days, activities, costs, and stay).
        """
        city_days: list[ItineraryDay] = []
        for i in range(subtask.allocated_days):
            day = self.day_worker.plan_day(
                day_num=i + 1,
                city=subtask.target_city,
                budget_for_day=daily_budget,
            )
            city_days.append(day)

        stay = self.stay_worker.select_stay(
            city=subtask.target_city,
            night_budget=daily_budget * 0.40,
            travelers=subtask.context.get("travelers", 1),
        )

        return {
            "city": subtask.target_city,
            "days": city_days,
            "stay": stay,
        }

    def orchestrate_itinerary(self, inputs: dict[str, Any]) -> TripItinerary:
        """
        Orchestrates full trip generation:
        1. Orchestrator breaks down trip into per-city day/budget allocations and transit links.
        2. Workers execute concurrently in parallel worker threads (one per city).
        3. Synthesizer merges the city plans into a coherent whole-trip itinerary.
        """
        blueprint = self.breakdown_trip(inputs)
        daily_budget = blueprint.total_budget / max(1, blueprint.total_days)

        # 1. Dispatch worker agents concurrently (one per city) via ThreadPoolExecutor
        city_results: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(blueprint.city_allocations))) as executor:
            future_to_city = {
                executor.submit(self._plan_city_worker, subtask, daily_budget): subtask.target_city
                for subtask in blueprint.city_allocations
            }
            for fut in as_completed(future_to_city):
                city_name = future_to_city[fut]
                city_results[city_name] = fut.result()

        # 2. Synthesizer merges the city plans preserving chronological city sequence
        all_days: list[ItineraryDay] = []
        stays: list[AccommodationOption] = []
        day_counter = 1

        for subtask in blueprint.city_allocations:
            c_name = subtask.target_city
            worker_data = city_results.get(c_name)
            if not worker_data:
                continue

            for day_item in worker_data["days"]:
                # Renumber day consecutively for the synthesized whole-trip schedule
                day_item.day_number = day_counter
                all_days.append(day_item)
                day_counter += 1

            if worker_data.get("stay"):
                stays.append(worker_data["stay"])

        # 3. Dispatch TransitWorker to synthesize sequential transit links
        transit_budget = daily_budget * 0.15 * blueprint.total_days
        transit = self.transit_worker.plan_transit(
            origin=blueprint.origin_city,
            cities=blueprint.destination_cities,
            total_transit_budget=transit_budget,
        )

        # 4. Synthesize final whole-trip TripItinerary
        primary_city = blueprint.destination_cities[0]
        cities_visited = blueprint.destination_cities if len(blueprint.destination_cities) > 1 else None

        itinerary = TripItinerary(
            destination_city=primary_city,
            origin_city=blueprint.origin_city,
            cities_visited=cities_visited,
            destination_country="India",
            trip_length_days=blueprint.total_days,
            currency=str(inputs.get("currency", "INR")),
            travelers=blueprint.travelers,
            total_estimated_cost=round(sum(d.estimated_cost for d in all_days) + transit.estimated_cost_per_person, 2),
            days=all_days,
            packing_suggestions=[
                "Comfortable walking shoes",
                "Weather-appropriate clothing",
                "Government ID & tickets",
                "Power bank & multi-city transit passes",
            ],
            intercity_transport=transit,
            recommended_stay=stays[0] if stays else None,
            recommended_stays=stays if len(stays) > 1 else None,
            orchestrator_used=True,
        )

        return itinerary

