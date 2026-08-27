"""
FastAPI web server for the AI Trip Planner application.
Serves static assets and provides REST API endpoints to trigger and stream multi-agent runs.
"""

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI(
    title="AI Trip Planner API",
    description="Multi-agent trip planning engine powered by CrewAI and Groq",
    version="1.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


class TripRequest(BaseModel):
    origin: str = Field(default="Bengaluru", description="Departure city or hub")
    cities: str = Field(default="Manali, Munnar, Goa", description="Candidate destination cities")
    interests: str = Field(default="hiking, food, waterfalls, culture", description="Traveler interests")
    trip_length: int = Field(default=5, ge=1, le=30, description="Trip length in days")
    budget: float = Field(default=25000, gt=0, description="Total budget amount")
    currency: str = Field(default="INR", description="Currency symbol/code: INR, USD, EUR, GBP")
    travel_mode: str = Field(default="domestic", description="Travel scope: domestic (India) or international")
    food_preference: str | None = Field(default=None, description="Dietary preferences like Pure Veg, Jain, Non-Veg")
    travel_style: str | None = Field(default=None, description="Travel style: budget, standard, luxury, family")


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    model = os.getenv("TRIP_PLANNER_MODEL", "groq/openai/gpt-oss-120b")
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "status": "healthy",
        "model": model,
        "groq_configured": str(has_groq),
        "openai_configured": str(has_openai),
    }


def _run_crew_sync(inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute CrewAI kickoff synchronously in a worker thread."""
    from trip_planner.crew import TripPlannerCrew
    crew = TripPlannerCrew().crew()
    result = crew.kickoff(inputs=inputs)
    
    if result.pydantic:
        data = result.pydantic.model_dump()
        if "currency" not in data or not data["currency"]:
            data["currency"] = inputs.get("currency", "INR")
        return data
    elif result.json_dict:
        return result.json_dict
    else:
        # If output was returned as raw text or JSON string
        import json
        raw = str(result.raw).strip()
        if raw.startswith("```json"):
            raw = raw.replace("```json", "").replace("```", "").strip()
        elif raw.startswith("```"):
            raw = raw.replace("```", "").strip()
        try:
            parsed = json.loads(raw)
            return parsed
        except Exception:
            return {"raw_output": raw}


@app.post("/api/plan-trip")
async def plan_trip(request: TripRequest) -> dict[str, Any]:
    """Plan a trip using the multi-agent pipeline."""
    # Phase 1 Allowlist Gate: Only "domestic" (or missing/empty, defaulting to "domestic") is allowed
    raw_mode = (request.travel_mode or "").strip().lower()
    mode = raw_mode if raw_mode else "domestic"
    if mode != "domestic":
        raise HTTPException(
            status_code=400,
            detail="Global / International destination mode is planned for Phase 2. Phase 1 (India Edition) currently supports domestic Indian destinations.",
        )

    # Compose enriched interests with dietary and style preferences
    combined_interests = request.interests.strip()
    if request.food_preference and request.food_preference.strip():
        combined_interests += f" (Food Preference: {request.food_preference.strip()})"
    if request.travel_style and request.travel_style.strip():
        combined_interests += f" (Travel Style: {request.travel_style.strip()})"

    currency_sym = "₹" if request.currency.upper() == "INR" else ("$" if request.currency.upper() == "USD" else request.currency)
    formatted_budget = f"{currency_sym}{int(request.budget):,} {request.currency.upper()}"

    inputs = {
        "origin": request.origin.strip(),
        "cities": request.cities.strip(),
        "interests": combined_interests,
        "trip_length": str(request.trip_length),
        "budget": formatted_budget,
        "currency": request.currency.upper(),
    }

    try:
        itinerary = await asyncio.to_thread(_run_crew_sync, inputs)
        if isinstance(itinerary, dict) and "currency" not in itinerary:
            itinerary["currency"] = request.currency.upper()
        return {
            "success": True,
            "inputs": inputs,
            "itinerary": itinerary,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {str(exc)}",
        ) from exc


# Mount static directory
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Frontend index.html not found")


def start_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    print(f"\n🚀 AI Trip Planner Web App running at: http://{host}:{port}\n")
    uvicorn.run("trip_planner.web.app:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
