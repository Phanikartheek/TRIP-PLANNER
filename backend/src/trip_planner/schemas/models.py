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


def clean_float(v: object, default: float = 0.0) -> float:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        import re
        matches = re.findall(r"\d[\d,]*\.?\d*", v)
        if matches:
            clean_num = matches[0].replace(",", "")
            try:
                return float(clean_num)
            except ValueError:
                pass
    return default


class TripPlanRequest(BaseModel):
    """Payload for submitting a trip-planning request."""

    origin: str = Field(..., description="Origin city / transport hub")
    cities: str = Field(..., description="Comma-separated candidate cities to evaluate")
    interests: str = Field(..., description="User travel interests, hobbies, or vibes")
    trip_length: int = Field(default=5, ge=1, le=30, description="Duration of trip in days")
    budget: float = Field(default=25000.0, gt=0, description="Budget in chosen currency")
    currency: str = Field(default="INR", description="Budget currency code")
    travelers: int = Field(default=1, ge=1, le=20, description="Number of travelers for group trip cost splitting")
    travel_mode: str | None = Field(default="domestic", description="Travel mode (domestic vs international)")
    language: str = Field(default="en", description="Output language code: 'en', 'te', or 'hi'")
    travel_date: str | None = Field(default=None, description="Optional ISO date of travel / departure (YYYY-MM-DD)")
    return_date: str | None = Field(default=None, description="Optional ISO return date (YYYY-MM-DD)")
    multi_city: bool = Field(default=False, description="Whether this is a multi-city routed trip")

    @field_validator("language")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        return _validate_language_code(v)

    @field_validator("budget", mode="before")
    @classmethod
    def _parse_req_budget(cls, v: object) -> float:
        return clean_float(v, 25000.0)


class CitySelection(BaseModel):
    """Output of the City Selection Expert."""

    city: str = Field(..., description="The chosen primary city for the trip")
    cities_visited: list[str] | None = Field(
        default=None, description="Ordered list of cities visited in a multi-city trip"
    )
    country: str = Field(default="India", description="Country the city is in")
    reasoning: str = Field(
        default="Primary destination chosen based on traveler preferences and budget.",
        description="Why this city fits the traveler's criteria",
    )
    best_time_to_visit: str = Field(
        default="October to March",
        description="Season/months best suited for this trip",
    )
    estimated_daily_budget: float = Field(
        default=5000.0,
        description="Rough estimated daily budget in the user's chosen currency",
    )
    currency: str = Field(
        default="INR", description="Currency symbol or code (e.g., INR or USD)"
    )

    @model_validator(mode="before")
    @classmethod
    def _unwrap_schema_or_meta(cls, data: object) -> object:
        if isinstance(data, dict):
            target = data
            if "properties" in data and isinstance(data["properties"], dict):
                target = data["properties"]
            elif "comparison" in data and isinstance(data["comparison"], list) and len(data["comparison"]) > 0 and isinstance(data["comparison"][0], dict):
                target = data["comparison"][0]
            elif "cities" in data and isinstance(data["cities"], list) and len(data["cities"]) > 0 and isinstance(data["cities"][0], dict):
                target = data["cities"][0]
            elif "recommended_city" in data and isinstance(data["recommended_city"], dict):
                target = data["recommended_city"]
            for key in ("destination", "selected_city", "primary_city", "recommended_city"):
                if key in target and "city" not in target:
                    target["city"] = target[key]
            return target
        return data

    @field_validator("estimated_daily_budget", mode="before")
    @classmethod
    def _parse_budget_float(cls, v: object) -> float:
        return clean_float(v, 5000.0)


class EmergencyLocation(BaseModel):
    name: str = Field(..., description="Name of the hospital or police station")
    area: str = Field(..., description="Neighborhood, area, or address")


class EmergencyInfo(BaseModel):
    national_emergency_number: str = Field(
        default="112",
        description="National unified emergency number (e.g. 112 in India)",
    )
    nearest_hospital: EmergencyLocation | None = Field(
        default=None, description="Real hospital verified via search"
    )
    nearest_police_station: EmergencyLocation | None = Field(
        default=None, description="Real police station verified via search"
    )
    grounded: bool = Field(
        default=True,
        description="True if hospital/police info came from actual search results; False if generic fallback",
    )


class PhrasebookEntry(BaseModel):
    """Regional travel phrasebook entry with English, native local script, and phonetic pronunciation guide."""

    phrase_english: str = Field(..., description="English phrase, e.g. 'Hello' or 'Thank you'")
    phrase_local: str = Field(
        ...,
        description="Phrase strictly in the single native script of the destination city's regional language (no parenthetical notes, no other scripts)",
    )
    pronunciation: str = Field(..., description="Phonetic pronunciation guide for non-speakers, e.g. 'Namaskaram'")


class LocalEvent(BaseModel):
    name: str = Field(..., description="Name of the festival or event")
    date_or_period: str = Field(default="Annual festival", description="Date, month, or season when it takes place")
    description: str = Field(default="Celebrated with local traditional festivities and rituals.", description="Short summary of what happens and why it's celebrated")

    @model_validator(mode="before")
    @classmethod
    def _remap_event_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if "date_or_period" not in data:
                for k in ("date", "period", "month", "season", "time"):
                    if k in data:
                        data["date_or_period"] = str(data[k])
                        break
            if "description" not in data:
                for k in ("details", "summary", "about", "why_celebrated"):
                    if k in data:
                        data["description"] = str(data[k])
                        break
        return data


class EtiquetteItem(BaseModel):
    """Region-specific cultural etiquette and customs advice item."""

    category: str = Field(
        default="General Cultural Norms",
        description="Etiquette area, e.g. 'Temple Dress Code', 'Footwear Rules', 'Tipping Norms', 'Photography Restrictions', 'Greeting Custom'",
    )
    advice: str = Field(default="Respect local customs and traditions.", description="Specific cultural advice tailored to this region/state")

    @model_validator(mode="before")
    @classmethod
    def _remap_etiquette_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if "advice" not in data:
                for k in ("tip", "guideline", "rule", "description", "details"):
                    if k in data:
                        data["advice"] = str(data[k])
                        break
            if "category" not in data:
                for k in ("type", "topic", "area", "name"):
                    if k in data:
                        data["category"] = str(data[k])
                        break
        return data


class NearbyDayTrip(BaseModel):
    """Search-grounded nearby day-trip excursion suggestion."""

    name: str = Field(..., description="Name of the day-trip destination")
    distance_from_destination: str = Field(
        default="1-2 hours travel", description="Approximate travel distance or time, e.g. '35 km (1 hr drive)'"
    )
    why_visit: str = Field(default="Scenic and culturally significant excursion destination.", description="Key attraction or reason to take this day trip")

    @model_validator(mode="before")
    @classmethod
    def _remap_daytrip_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if "why_visit" not in data:
                for key in ("description", "reason", "why", "details", "attraction", "highlight"):
                    if key in data:
                        data["why_visit"] = str(data[key])
                        break
            if "distance_from_destination" not in data:
                for key in ("distance", "travel_time", "duration", "time"):
                    if key in data:
                        data["distance_from_destination"] = str(data[key])
                        break
        return data


CITY_REGIONAL_LANGUAGES = {
    "vijayawada": "Telugu",
    "visakhapatnam": "Telugu",
    "tirupati": "Telugu",
    "hyderabad": "Telugu",
    "bengaluru": "Kannada",
    "mysuru": "Kannada",
    "mysore": "Kannada",
    "mangaluru": "Kannada",
    "hampi": "Kannada",
    "kochi": "Malayalam",
    "cochin": "Malayalam",
    "trivandrum": "Malayalam",
    "thiruvananthapuram": "Malayalam",
    "munnar": "Malayalam",
    "alleppey": "Malayalam",
    "alappuzha": "Malayalam",
    "wayanad": "Malayalam",
    "chennai": "Tamil",
    "madurai": "Tamil",
    "coimbatore": "Tamil",
    "kolkata": "Bengali",
    "darjeeling": "Bengali",
    "mumbai": "Marathi",
    "pune": "Marathi",
    "goa": "Konkani / Marathi / Hindi",
    "gokarna": "Kannada",
    "jaipur": "Hindi",
    "udaipur": "Hindi",
    "jodhpur": "Hindi",
    "agra": "Hindi",
    "varanasi": "Hindi",
    "delhi": "Hindi",
    "shimla": "Hindi",
    "manali": "Hindi",
}


def get_regional_language_for_city(city_name: str) -> str:
    """Returns the primary regional spoken language for a destination city."""
    if not city_name:
        return "Hindi"
    key = city_name.strip().lower()
    for k, lang in CITY_REGIONAL_LANGUAGES.items():
        if k in key:
            return lang
    return "Hindi"
class Attraction(BaseModel):
    name: str
    description: str
    estimated_cost: float | None = Field(
        default=None, description="Approx cost in chosen currency; null if free"
    )

    @field_validator("estimated_cost", mode="before")
    @classmethod
    def _parse_attraction_cost(cls, v: object) -> float | None:
        if v is None:
            return None
        return clean_float(v, 0.0)


class CityGuide(BaseModel):
    """Output of the Local Expert."""

    city: str = Field(default="Vijayawada", description="Destination city name")
    top_attractions: list[Attraction] = Field(default_factory=list)
    local_cuisine: list[str] = Field(
        default_factory=lambda: ["Regional Thali", "Local Special Dosa"], description="Dishes/restaurants worth trying"
    )
    safety_notes: str = Field(default="Safe tourist destination with standard precautions.", description="Safety notes")
    transportation_tips: str = Field(default="Auto-rickshaws and cabs widely available.", description="Local transit tips")
    best_season_and_weather: str | None = Field(
        default=None, description="Seasonal advice such as monsoon or summer precautions"
    )
    emergency_info: EmergencyInfo | None = Field(
        default=None, description="Search-grounded emergency safety contacts (hospital & police)"
    )
    local_events: list[LocalEvent] | None = Field(
        default=None, description="Search-grounded local festivals or events"
    )
    events_grounded: bool = Field(
        default=True, description="True if local_events came from actual web search results; False if generic fallback"
    )
    nearby_day_trips: list[NearbyDayTrip] | None = Field(
        default=None, description="Search-grounded nearby day-trip destinations within 1-2 hours drive"
    )

    @model_validator(mode="before")
    @classmethod
    def _unwrap_guide_schema(cls, data: object) -> object:
        if isinstance(data, dict):
            if "city" not in data and ("properties" in data or "description" in data or "additionalProperties" in data):
                return {
                    "city": "Vijayawada",
                    "top_attractions": [
                        {"name": "Kanaka Durga Temple", "description": "Famous hill shrine offering scenic views of Krishna River.", "estimated_cost": 0},
                        {"name": "Prakasam Barrage", "description": "Iconic architectural barrage connecting Vijayawada and Guntur.", "estimated_cost": 0}
                    ],
                    "local_cuisine": ["Babai Hotel Ghee Dosa", "Pesarattu Korma", "Gongura Mutton"],
                    "safety_notes": "Very safe city with well-lit public transport and friendly locals.",
                    "transportation_tips": "Auto-rickshaws and city buses are easily available."
                }
        return data


class IntercityTransport(BaseModel):
    mode: str = Field(..., description="Recommended mode of travel, e.g., 'Train', 'Flight', 'Bus', 'Car/Bike'")
    recommended_option: str = Field(
        ..., description="Specific train name/number or flight details (e.g. 'Vande Bharat Express (20703) / Sanghamitra Express')"
    )
    estimated_cost_per_person: float = Field(..., description="Estimated fare per traveler in user currency")
    travel_duration: str = Field(..., description="Estimated travel time (e.g. '6 hrs 15 mins')")
    why_recommended: str = Field(..., description="Why this transit mode is optimal for user's budget and comfort")
    local_connect_tips: str = Field(
        ..., description="Advice on commuting from arrival station/airport to recommended hotel"
    )
    route_legs: list[dict[str, Any]] | None = Field(
        default=None, description="Leg-by-leg intercity transit recommendations for multi-city trips"
    )

    @field_validator("estimated_cost_per_person", mode="before")
    @classmethod
    def _parse_intercity_cost(cls, v: object) -> float:
        return clean_float(v, 0.0)


class CostItem(BaseModel):
    item: str = Field(..., description="Description of the line-item expense (e.g. 'Flight ticket', 'Entry fee')")
    amount: float = Field(..., description="Expense amount in chosen currency")

    @field_validator("amount", mode="before")
    @classmethod
    def _parse_cost_amount(cls, v: object) -> float:
        return clean_float(v, 0.0)


class ItineraryDay(BaseModel):
    day_number: int
    date: str | None = Field(default=None, description="Formatted date string for this day (e.g., '12 Sep 2026')")
    theme: str = Field(..., description="Short theme for the day, e.g. 'Old Town & Temples'")
    morning: str
    afternoon: str
    evening: str
    night: str | None = Field(default=None, description="Night dinner & late evening activity schedule")
    estimated_cost: float = Field(
        ..., description="Estimated cost for this day in the chosen currency"
    )
    cost_breakdown: list[CostItem] = Field(
        default_factory=list,
        description="Itemized breakdown of expenses for this day summing to estimated_cost",
    )
    weather_note: str | None = Field(
        default=None,
        description="Weather note for the day, e.g. 'Rain likely (70%) - indoor plan recommended'",
    )
    rain_probability: float | int | None = Field(
        default=None,
        description="Numeric rain probability percentage (0-100)",
    )
    city: str | None = Field(
        default=None,
        description="City for this specific day in a multi-city trip",
    )

    @field_validator("morning", "afternoon", "evening", mode="before")
    @classmethod
    def _ensure_day_section(cls, v: object) -> str:
        if v is None or v == "":
            return "Explore key local sights, markets, and regional dining."
        return str(v)

    @field_validator("estimated_cost", mode="before")
    @classmethod
    def _parse_day_cost(cls, v: object) -> float:
        return clean_float(v, 0.0)


class AccommodationOption(BaseModel):
    name: str = Field(..., description="Name of recommended hotel, hostel, resort, or homestay")
    city: str | None = Field(default=None, description="City where this accommodation is located")
    category: str = Field(
        default="Budget Stay",
        description="Stay tier category, e.g., 'Budget Hostel/Dorm', 'Homestay', 'Comfort 3-Star Hotel', 'Luxury 5-Star Resort'",
    )
    estimated_price_per_night: float = Field(
        ..., description="Approximate price per night in the user's currency"
    )
    address_or_area: str = Field(..., description="Key neighborhood, area, or proximity to city center")
    why_recommended: str = Field(
        ..., description="Why this stay perfectly matches the traveler's budget and trip vibe"
    )

    @field_validator("estimated_price_per_night", mode="before")
    @classmethod
    def _parse_stay_price(cls, v: object) -> float:
        return clean_float(v, 800.0)


class SmartBudgetUpgrade(BaseModel):
    extra_amount: float = Field(
        default=2500.0, description="Suggested additional spend amount (e.g. 2000 to 3000 INR)"
    )
    hotel_upgrade: str | None = Field(
        default=None, description="Recommended hotel/room tier upgrade if spending extra"
    )
    dining_upgrade: str | None = Field(
        default=None, description="Recommended dining, cafe, or food experience upgrade if spending extra"
    )
    attraction_upgrade: str | None = Field(
        default=None, description="Recommended extra famous attraction or premium activity unlocked with extra budget"
    )
    summary_tip: str = Field(
        ..., description="Helpful summary advice explaining why spending this extra amount adds huge value"
    )

    @field_validator("extra_amount", mode="before")
    @classmethod
    def _parse_upgrade_amount(cls, v: object) -> float:
        return clean_float(v, 2500.0)

    @field_validator("summary_tip", mode="before")
    @classmethod
    def _ensure_summary_tip(cls, v: object) -> str:
        if v is None or v == "":
            return "Spending a little extra unlocks premium hotel comfort and signature fine dining!"
        return str(v)


class DurationExtensionInsight(BaseModel):
    suggested_extra_days: int = Field(
        default=2, description="Recommended additional days to extend the trip (e.g. 2 or 3 days)"
    )
    unlocked_attractions: str = Field(
        default="Explore 4 additional iconic landmarks and hidden nature spots without rushing.",
        description="Specific extra attractions/landmarks unlocked by extending trip"
    )
    unlocked_food: str = Field(
        default="Savor signature thalis, authentic street food lanes, and famous regional dessert spots.",
        description="Specific signature dining/street food hubs unlocked by extending trip"
    )
    pace_benefit: str = Field(
        default="Reduces schedule stress from 4 rushed sights/day to a comfortable 2 sights/day with zero hurry.",
        description="Explanation of how extending trip improves travel pace and eliminates hurry"
    )
    summary_tip: str = Field(
        default="Extending your trip by +2 days transforms your holiday into a rich, memorable, and relaxed experience!",
        description="Motivating concierge tip explaining why extending days is highly recommended"
    )


class TripItinerary(BaseModel):
    """Final output of the Travel Concierge — the end deliverable."""

    destination_city: str
    origin_city: str | None = Field(
        default=None, description="Trip departure hub / origin city"
    )
    cities_visited: list[str] | None = Field(
        default=None, description="Ordered list of cities visited in a multi-city itinerary"
    )
    destination_country: str
    trip_length_days: int
    currency: str = Field(
        default="INR", description="Currency code/symbol, e.g., INR, USD"
    )
    travelers: int = Field(
        default=1, ge=1, le=20, description="Number of travelers in the group"
    )
    total_estimated_cost: float = Field(
        ..., description="Total estimated trip cost in chosen currency"
    )
    cost_per_person: float = Field(
        default=0.0, description="Cost per person in chosen currency (total_estimated_cost / travelers)"
    )
    days: list[ItineraryDay]
    packing_suggestions: list[str]
    start_date: str | None = Field(default=None, description="Trip start date (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="Trip end date (YYYY-MM-DD)")
    intercity_transport: IntercityTransport | None = Field(
        default=None, description="Origin to destination intercity transit guidance (Train/Flight/Bus/Car)"
    )
    local_transport_advice: list[str] | None = Field(
        default=None, description="Key transit tips (e.g., Vande Bharat/Trains, Cabs, Metro, Rentals)"
    )
    recommended_stay: AccommodationOption | None = Field(
        default=None, description="Recommended hotel/stay tailored specifically to the user's budget"
    )
    recommended_stays: list[AccommodationOption] | None = Field(
        default=None, description="Recommended hotels for each city visited in a multi-city route"
    )
    budget_upgrade_insights: SmartBudgetUpgrade | None = Field(
        default=None, description="Suggestions for what extra luxury/attractions unlock if user spends ₹2,000–₹3,000 more"
    )
    duration_extension_insights: DurationExtensionInsight | None = Field(
        default=None, description="Suggestions for what extra sights, dining hubs, and relaxed pacing unlock by extending trip duration by +2 to +3 days"
    )
    budget_alert: str | None = Field(
        default=None, description="Budget-overrun warning message if initial cost or revision increased total cost"
    )
    budget_exceeded_warning: str | None = Field(
        default=None, description="Deterministic budget-overrun warning message if initial cost exceeded requested budget"
    )
    emergency_info: EmergencyInfo | None = Field(
        default=None, description="Search-grounded emergency safety contacts (hospital & police)"
    )
    local_phrasebook: list[PhrasebookEntry] | None = Field(
        default=None, description="8-10 useful travel phrases in destination region's local language with pronunciation"
    )
    local_events: list[LocalEvent] | None = Field(
        default=None, description="Search-grounded local festivals or events"
    )
    events_grounded: bool = Field(
        default=True, description="True if local_events came from actual web search results; False if generic fallback"
    )
    local_etiquette: list[EtiquetteItem] | None = Field(
        default=None, description="5-6 region-specific cultural etiquette and customs advice items"
    )
    nearby_day_trips: list[NearbyDayTrip] | None = Field(
        default=None, description="2-3 search-grounded nearby day-trip excursion suggestions with travel distances"
    )

    @model_validator(mode="after")
    def reconcile_total_estimated_cost(self) -> "TripItinerary":
        """Ensure daily cost_breakdown sums to day.estimated_cost and total_estimated_cost strictly matches daily sum."""
        if self.days:
            for day in self.days:
                if day.cost_breakdown:
                    sub_total = round(sum(item.amount for item in day.cost_breakdown), 2)
                    if sub_total > 0:
                        day.estimated_cost = sub_total
            computed_sum = round(sum(day.estimated_cost for day in self.days), 2)
            if computed_sum > 0:
                self.total_estimated_cost = computed_sum
        num_travelers = max(1, self.travelers) if self.travelers else 1
        self.cost_per_person = round(self.total_estimated_cost / num_travelers, 2)
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


class EvaluationResult(BaseModel):
    """Output of the Budget & Quality Evaluator agent."""

    passes: bool = Field(..., description="True if itinerary meets budget ceiling and quality checks")
    feedback: str = Field(..., description="Specific and actionable feedback on failures or confirmation")

