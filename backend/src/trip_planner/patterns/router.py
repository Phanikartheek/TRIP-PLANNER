"""
Routing Pattern for AI Trip Planner.
Classifies traveler intent, persona, trip topology, and regional constraints
to dynamically select specialized agent prompts, tools, and budget guardrails.
"""

import re
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class UserIntent(str, Enum):
    NEW_TRIP = "new_trip"
    REVISION = "revision"
    QUESTION = "question"
    COMPARISON = "comparison"


class IntentClassificationResult(BaseModel):
    intent: UserIntent
    confidence: float = 1.0
    extracted_params: dict[str, Any] = Field(default_factory=dict)


class TripTopology(str, Enum):
    SINGLE_CITY = "single_city"
    MULTI_CITY = "multi_city"
    WEEKEND_GETAWAY = "weekend_getaway"
    EXPEDITION = "expedition"


class TravelerPersona(str, Enum):
    BUDGET_BACKPACKER = "budget_backpacker"
    FAMILY_LEISURE = "family_leisure"
    LUXURY_COMFORT = "luxury_comfort"
    HERITAGE_CULTURE = "heritage_culture"
    ADVENTURE = "adventure"


class RouteDecision(BaseModel):
    """Result of request classification directing subsequent pipeline stages."""
    topology: TripTopology
    persona: TravelerPersona
    recommended_focus: list[str] = Field(default_factory=list)
    system_prompt_addon: str = ""
    budget_guardrail: dict[str, float] = Field(default_factory=dict)
    special_cautions: list[str] = Field(default_factory=list)


class TripRouter:
    """
    Intelligent router evaluating user inputs to determine optimal agent workflow.
    """

    @classmethod
    def classify_intent(cls, text: str, has_active_job: bool = False) -> IntentClassificationResult:
        """
        Fast regex-assisted intent classifier categorizing queries into:
        - new_trip: Generate a new itinerary
        - revision: Modify an existing itinerary
        - question: Destination Q&A / advice
        - comparison: Compare two destinations
        """
        clean = text.strip()
        low = clean.lower()

        # 1. Comparison Intent
        comp_patterns = [
            r"\b(?:compare|comparison|versus|vs\.?)\b",
            r"\bdifference between\b",
            r"\bwhich (?:one )?is better\b",
            r"\bbetter between\b",
            r"\bshould i (?:go to|visit|choose) [a-zA-Z\s]+ or [a-zA-Z\s]+",
        ]
        for pat in comp_patterns:
            if re.search(pat, low):
                cities = []
                vs_match = re.search(r"([A-Za-z\s]+?)\s+(?:vs\.?|versus|or|compared to|and)\s+([A-Za-z\s]+)", clean, re.IGNORECASE)
                if vs_match:
                    c1 = vs_match.group(1).split()[-1].strip(" ,?")
                    c2 = vs_match.group(2).split()[0].strip(" ,?")
                    if len(c1) > 2 and len(c2) > 2:
                        cities = [c1.capitalize(), c2.capitalize()]
                return IntentClassificationResult(
                    intent=UserIntent.COMPARISON,
                    confidence=0.95,
                    extracted_params={"cities": cities, "raw_query": clean},
                )

        # 2. Revision Intent
        rev_patterns = [
            r"\b(?:revise|revision|modify|update|reschedule|replan)\b",
            r"\b(?:change|swap|replace|remove|delete|add|extend)\b.*?\b(?:day|hotel|resort|flight|activity|stay|cost|budget|itinerary|hostel)\b",
            r"\bmake\s+(?:it|this|day\s*\d+|trip)?\s*(?:cheaper|more affordable|more budget friendly|faster|shorter|longer)\b",
            r"\b(?:reduce|cut|tighten)\s+(?:the\s+)?budget\b",
            r"\binstead of\b",
            r"\bchange (?:the\s+)?itinerary\b",
        ]
        is_rev = any(re.search(pat, low) for pat in rev_patterns)
        if has_active_job and (
            is_rev
            or low.startswith(
                (
                    "change",
                    "swap",
                    "replace",
                    "make",
                    "can we",
                    "please",
                    "remove",
                    "add",
                    "switch",
                    "adjust",
                    "update",
                )
            )
        ):
            return IntentClassificationResult(
                intent=UserIntent.REVISION,
                confidence=0.95,
                extracted_params={"feedback": clean},
            )
        elif is_rev:
            return IntentClassificationResult(
                intent=UserIntent.REVISION,
                confidence=0.90,
                extracted_params={"feedback": clean},
            )

        # 3. Destination Q&A Intent
        qa_patterns = [
            r"^(?:what|where|how|why|when|is it|can i|can we|are there|is there|do they|could you tell me)\b",
            r"\b(?:best time to visit|how to reach|is it safe|what should i eat|where to eat|recommend a|suggest a)\b",
            r"\b(?:entry fee|ticket price|opening hours|dress code|weather in)\b",
        ]
        is_question = any(re.search(pat, low) for pat in qa_patterns)
        if is_question or (clean.endswith("?") and not any(kw in low for kw in ["plan", "itinerary", "days trip"])):
            return IntentClassificationResult(
                intent=UserIntent.QUESTION,
                confidence=0.90,
                extracted_params={"question": clean},
            )

        # 4. New Trip Intent
        days = 3
        days_match = re.search(r"(\d+)\s*(?:-| )*(?:day|days)", low)
        if days_match:
            days = int(days_match.group(1))
        elif "weekend" in low:
            days = 2
        elif "week" in low:
            days = 7

        budget = 20000.0
        budget_match = re.search(r"(?:₹|rs\.?|inr|budget\s*of|under\s*₹?)\s*(\d+(?:,\d+)*(?:\s*k)?)", low)
        if budget_match:
            raw_b = budget_match.group(1).replace(",", "")
            if raw_b.endswith("k"):
                budget = float(raw_b[:-1]) * 1000.0
            else:
                budget = float(raw_b)

        origin = "Delhi"
        origin_match = re.search(r"(?:from|starting in|departing from)\s+([A-Za-z]+)", clean, re.IGNORECASE)
        if origin_match:
            origin = origin_match.group(1).capitalize()

        dest_match = re.search(r"(?:to|in|visit|explore|trip to)\s+([A-Za-z]+)", clean, re.IGNORECASE)
        destination = dest_match.group(1).capitalize() if dest_match else "Goa"

        return IntentClassificationResult(
            intent=UserIntent.NEW_TRIP,
            confidence=0.85,
            extracted_params={
                "cities": destination,
                "origin": origin,
                "trip_length": days,
                "budget": budget,
                "interests": clean,
            },
        )


    @classmethod
    def classify(cls, inputs: dict[str, Any]) -> RouteDecision:
        """
        Classifies trip parameters into topology and persona with tailored guardrails.
        """
        cities_raw = str(inputs.get("cities", "")).strip()
        city_list = [c.strip() for c in cities_raw.split(",") if c.strip()]
        is_multi = bool(inputs.get("multi_city")) or len(city_list) > 1

        days = int(inputs.get("trip_length", inputs.get("days", 3)))
        budget = float(inputs.get("budget", 25000.0))
        travelers = max(1, int(inputs.get("travelers", 1)))
        budget_per_person_day = budget / (travelers * max(1, days))

        interests = str(inputs.get("interests", "")).lower()

        # 1. Determine Topology
        if is_multi and len(city_list) > 1:
            topology = TripTopology.MULTI_CITY
        elif days <= 2:
            topology = TripTopology.WEEKEND_GETAWAY
        elif days >= 7:
            topology = TripTopology.EXPEDITION
        else:
            topology = TripTopology.SINGLE_CITY

        # 2. Determine Persona
        if any(w in interests for w in ["luxury", "resort", "5 star", "fine dining", "spa"]) or budget_per_person_day >= 6000:
            persona = TravelerPersona.LUXURY_COMFORT
        elif any(w in interests for w in ["trek", "hike", "rafting", "safari", "camping", "adventure"]):
            persona = TravelerPersona.ADVENTURE
        elif any(w in interests for w in ["temple", "heritage", "history", "monument", "culture", "museum"]):
            persona = TravelerPersona.HERITAGE_CULTURE
        elif any(w in interests for w in ["family", "kids", "elderly", "parents"]) or travelers >= 3:
            persona = TravelerPersona.FAMILY_LEISURE
        elif budget_per_person_day < 2000 or any(w in interests for w in ["hostel", "budget", "backpacker", "cheap"]):
            persona = TravelerPersona.BUDGET_BACKPACKER
        else:
            persona = TravelerPersona.FAMILY_LEISURE

        # 3. Formulate persona-specific guardrails & prompt addons
        focus: list[str] = []
        cautions: list[str] = []
        prompt_addon = ""
        guardrails: dict[str, float] = {}

        if persona == TravelerPersona.BUDGET_BACKPACKER:
            focus = ["Hostels & Budget Stays", "Authentic Street Food", "Public Transit & Walking", "Free/Low-cost Attractions"]
            prompt_addon = "Prioritize clean, highly-rated budget stays (Zostel/hostels), authentic affordable local eateries, and public transit (metro/bus/train)."
            guardrails = {"stays": 0.30, "food": 0.25, "transit": 0.20, "activities": 0.15, "contingency": 0.10}
            cautions.append("Keep per-night stay cost under ₹1,000 where feasible.")

        elif persona == TravelerPersona.LUXURY_COMFORT:
            focus = ["Premium 4/5-star Hotels & Resorts", "Fine Dining & Chef Tastings", "Private Cabs / Express Transit", "Exclusive Guided Tours"]
            prompt_addon = "Focus on top-tier hospitality, curated premium experiences, comfortable private air-conditioned transit, and iconic culinary dining."
            guardrails = {"stays": 0.45, "food": 0.25, "transit": 0.15, "activities": 0.10, "contingency": 0.05}

        elif persona == TravelerPersona.ADVENTURE:
            focus = ["Outdoor Trails & Treks", "Adventure Sports Gear", "Scenic Landscapes", "Active Day Pacing"]
            prompt_addon = "Plan for early morning starts, physical stamina requirements, local certified adventure operators, and scenic nature stops."
            guardrails = {"stays": 0.30, "food": 0.20, "transit": 0.20, "activities": 0.20, "contingency": 0.10}
            cautions.append("Check seasonal weather and trail conditions; include safety reminders.")

        elif persona == TravelerPersona.HERITAGE_CULTURE:
            focus = ["Historical Monuments & UNESCO Sites", "Traditional Artisan Markets", "Regional Cuisine & Cooking Classes", "Local Etiquette"]
            prompt_addon = "Emphasize architectural history, opening times, ticket booking rules, certified heritage guides, and cultural dress etiquette."
            guardrails = {"stays": 0.35, "food": 0.25, "transit": 0.15, "activities": 0.15, "contingency": 0.10}

        else: # FAMILY_LEISURE
            focus = ["Comfortable Family Hotels", "Kid/Elderly Friendly Sightseeing", "Relaxed Afternoon Breaks", "Reliable Clean Dining"]
            prompt_addon = "Ensure gentle pacing with built-in rest stops, clean hygienic dining, minimal transit exhaustion, and family-friendly attractions."
            guardrails = {"stays": 0.40, "food": 0.25, "transit": 0.15, "activities": 0.10, "contingency": 0.10}
            cautions.append("Avoid rushing more than 2-3 activities per day.")

        if topology == TripTopology.MULTI_CITY:
            cautions.append("Optimize intercity transit corridor sequentially to minimize backtracking.")

        return RouteDecision(
            topology=topology,
            persona=persona,
            recommended_focus=focus,
            system_prompt_addon=prompt_addon,
            budget_guardrail=guardrails,
            special_cautions=cautions,
        )
