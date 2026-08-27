"""
CLI entrypoint. Collects trip inputs, kicks off the crew, and prints the
final structured itinerary.

Kept deliberately thin: input-collection is I/O, `TripPlannerCrew` is the
actual logic. Separating them means the crew is testable without stdin,
and this file could be swapped for a FastAPI route or a Streamlit form
later without touching crew.py at all.
"""

import sys
from trip_planner.crew import TripPlannerCrew


def _prompt(label: str, default: str) -> str:
    try:
        value = input(f"{label} [{default}]: ").strip()
    except EOFError:
        print(f"{label} [{default}]: {default}")
        return default
    return value or default


def collect_inputs() -> dict:
    print("=== AI Trip Planner ===\n")
    origin = _prompt("Departing from", "Bengaluru")
    cities = _prompt("Candidate cities (comma-separated)", "Bali, Kyoto, Lisbon")
    interests = _prompt("Interests", "food, hiking, history")
    trip_length = _prompt("Trip length (days)", "5")
    budget = _prompt("Total budget (USD)", "1500")
    return {
        "origin": origin,
        "cities": cities,
        "interests": interests,
        "trip_length": trip_length,
        "budget": budget,
    }


def run() -> None:
    if "--web" in sys.argv or "-w" in sys.argv:
        from trip_planner.web.app import start_server
        start_server()
        return

    inputs = collect_inputs()
    result = TripPlannerCrew().crew().kickoff(inputs=inputs)

    print("\n=== Final Itinerary ===\n")
    # result.pydantic holds the validated TripItinerary from the last task
    # (CrewAI carries the final task's output_pydantic onto CrewOutput).
    if result.pydantic:
        print(result.pydantic.model_dump_json(indent=2))
    else:
        # Fallback: schema validation failed somewhere in the chain.
        # Surface the raw text rather than crashing, so the run isn't wasted.
        print("Could not parse structured output; raw result below:\n")
        print(result.raw)


if __name__ == "__main__":
    run()
