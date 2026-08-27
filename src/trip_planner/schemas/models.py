"""
Structured output contracts for each stage of the trip-planning pipeline.

Why this exists: CrewAI tasks can return raw text, but that makes the
pipeline brittle — the next agent (or your own downstream code) has to
re-parse free-form prose. Attaching a Pydantic model via `output_pydantic`
makes CrewAI validate the LLM's JSON output against a schema before it's
passed along, so failures surface immediately (a validation error) instead
of silently propagating a malformed string three stages later.
"""

from pydantic import BaseModel, Field, model_validator


class CitySelection(BaseModel):
    """Output of the City Selection Expert."""

    city: str = Field(..., description="The chosen city for the trip")
    country: str = Field(..., description="Country the city is in")
    reasoning: str = Field(
        ..., description="Why this city fits the traveler's criteria"
    )
    best_time_to_visit: str = Field(
        ..., description="Season/months best suited for this trip"
    )
    estimated_daily_budget: float = Field(
        ..., description="Rough estimated daily budget in the user's chosen currency"
    )
    currency: str = Field(
        default="INR", description="Currency symbol or code (e.g., INR or USD)"
    )


class Attraction(BaseModel):
    name: str
    description: str
    estimated_cost: float | None = Field(
        default=None, description="Approx cost in chosen currency; null if free"
    )


class CityGuide(BaseModel):
    """Output of the Local Expert."""

    city: str
    top_attractions: list[Attraction]
    local_cuisine: list[str] = Field(
        ..., description="Dishes/restaurants worth trying (including dietary options like Veg/Non-Veg)"
    )
    safety_notes: str
    transportation_tips: str
    best_season_and_weather: str | None = Field(
        default=None, description="Seasonal advice such as monsoon or summer precautions"
    )


class ItineraryDay(BaseModel):
    day_number: int
    theme: str = Field(..., description="Short theme for the day, e.g. 'Old Town & Temples'")
    morning: str
    afternoon: str
    evening: str
    estimated_cost: float = Field(
        ..., description="Estimated cost for this day in the chosen currency"
    )


class TripItinerary(BaseModel):
    """Final output of the Travel Concierge — the end deliverable."""

    destination_city: str
    destination_country: str
    trip_length_days: int
    currency: str = Field(
        default="INR", description="Currency code/symbol, e.g., INR, USD"
    )
    total_estimated_cost: float = Field(
        ..., description="Total estimated trip cost in chosen currency"
    )
    days: list[ItineraryDay]
    packing_suggestions: list[str]
    local_transport_advice: list[str] | None = Field(
        default=None, description="Key transit tips (e.g., Vande Bharat/Trains, Cabs, Metro, Rentals)"
    )

    @model_validator(mode="after")
    def reconcile_total_estimated_cost(self) -> "TripItinerary":
        """Ensure total_estimated_cost strictly matches the arithmetic sum of daily costs."""
        if self.days:
            computed_sum = round(sum(day.estimated_cost for day in self.days), 2)
            if computed_sum > 0:
                self.total_estimated_cost = computed_sum
        return self
