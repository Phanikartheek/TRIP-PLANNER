"""
Structured output contracts for each stage of the trip-planning pipeline.

Why this exists: CrewAI tasks can return raw text, but that makes the
pipeline brittle — the next agent (or your own downstream code) has to
re-parse free-form prose. Attaching a Pydantic model via `output_pydantic`
makes CrewAI validate the LLM's JSON output against a schema before it's
passed along, so failures surface immediately (a validation error) instead
of silently propagating a malformed string three stages later.
"""

import time
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

SUPPORTED_LANGUAGES = {"en", "te", "hi"}


def _validate_language_code(v: str) -> str:
    code = v.strip().lower()
    if code not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language code '{v}'. Supported languages are: 'en' (English), 'te' (Telugu), 'hi' (Hindi)."
        )
    return code


class TripPlanRequest(BaseModel):
    """Payload for submitting a trip-planning request."""

    origin: str = Field(..., description="Origin city / transport hub")
    cities: str = Field(..., description="Comma-separated candidate cities to evaluate")
    interests: str = Field(..., description="User travel interests, hobbies, or vibes")
    trip_length: int = Field(default=5, ge=1, le=30, description="Duration of trip in days")
    budget: float = Field(default=25000.0, gt=0, description="Budget in chosen currency")
    currency: str = Field(default="INR", description="Budget currency code")
    travel_mode: str | None = Field(default="domestic", description="Travel mode (domestic vs international)")
    language: str = Field(default="en", description="Output language code: 'en', 'te', or 'hi'")

    @field_validator("language")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        return _validate_language_code(v)


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


class RevisionRequest(BaseModel):
    """User request payload to revise an existing itinerary with conversational feedback."""

    job_id: str = Field(
        ..., description="ID of the completed trip planning job to revise"
    )
    feedback: str = Field(
        ..., description="User follow-up feedback, e.g. 'make day 2 cheaper' or 'replace trekking with beach time'"
    )
    language: str = Field(default="en", description="Output language code: 'en', 'te', or 'hi'")

    @field_validator("language")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        return _validate_language_code(v)


class QAExchange(BaseModel):
    """Represents a single conversational turn in the destination Q&A thread."""

    question: str = Field(..., description="The user's question")
    answer: str = Field(..., description="The expert's response")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of the exchange")
    grounded_claims: list[str] = Field(
        default_factory=list,
        description="Specific named places, facts, or prices verified via search/tools",
    )
    ungrounded_claims: list[str] = Field(
        default_factory=list,
        description="Claims stated from general knowledge without matching search results",
    )


class QAResponse(BaseModel):
    """Structured output contract for the Local Q&A Expert."""

    answer: str = Field(
        ...,
        description="Direct, helpful 3-6 sentence response with specific named establishments",
    )
    grounded_claims: list[str] = Field(
        default_factory=list,
        description="List of specific named places, prices, or facts directly verified from tool search results",
    )
    ungrounded_claims: list[str] = Field(
        default_factory=list,
        description="List of statements or advice based on general knowledge without tool verification (empty list if all grounded)",
    )
    sources: list[str] | None = Field(
        default=None,
        description="Optional reference URLs from search results",
    )


class DestinationQuestion(BaseModel):
    """User request payload to ask a direct question about a destination."""

    job_id: str = Field(
        ..., description="ID of the completed trip planning job to provide destination context"
    )
    question: str = Field(
        ..., description="User question about the destination (e.g. food, shopping, cafes, transport)"
    )
    conversation_history: list[QAExchange] | None = Field(
        default=None,
        description="Optional prior conversational exchanges in the same session",
    )
    language: str = Field(default="en", description="Output language code: 'en', 'te', or 'hi'")

    @field_validator("language")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        return _validate_language_code(v)


# Alias QuestionAnswer to QAResponse for backward compatibility
QuestionAnswer = QAResponse
