"""
Unit tests for Part B: Parallelization Pattern.
Verifies:
- Parallel researcher runs independent subtasks concurrently rather than blocking sequentially
- Emergency info and events grounding requirements are preserved
- ParallelCityResearchTool returns valid schema-compliant CityGuide JSON
"""

import json
import time

from trip_planner.patterns.parallelizer import (
    ParallelCityResearchTool,
    ParallelResearcher,
)
from trip_planner.schemas.models import CityGuide


def test_parallel_researcher_runs_tasks_independently():
    """
    Confirm that 5 independent subtasks execute concurrently in parallel worker threads.
    If run serially, 5 tasks with 0.1s sleep take >= 0.5s.
    Running in parallel takes ~0.1s - 0.25s.
    """
    def mock_delayed_search(query: str) -> str:
        time.sleep(0.1)
        if "emergency" in query:
            return "District Civil Hospital, Contact: 0866-2578888, Police: 100"
        if "festival" in query:
            return "Krishna Pushkaram Festival - Grand riverfront celebration"
        if "day trip" in query:
            return "Amaravathi Buddhist Stupa - 35 km (1 hr drive)"
        if "attraction" in query:
            return "Bhavani Island: Scenic river island retreat - Rs 50"
        return "Famous local Gongura Pachadi and Biryani"

    researcher = ParallelResearcher(max_workers=5, search_fn=mock_delayed_search)
    t0 = time.time()
    guide = researcher.gather_parallel_city_guide(city="Vijayawada", interests="temple, river")
    elapsed = time.time() - t0

    assert isinstance(guide, CityGuide)
    assert guide.city == "Vijayawada"
    # 5 tasks * 0.1s sleep: parallel execution should be well under 0.4s
    assert elapsed < 0.40, f"Expected parallel execution under 0.4s, got {elapsed:.2f}s (serial execution detected)"


def test_parallel_city_guide_preserves_grounding():
    """
    Ensure emergency contacts and local events are grounded in search results.
    """
    def mock_grounded_search(query: str) -> str:
        if "emergency" in query:
            return "Apollo Specialty Hospital, Jubilee Hills, Hyderabad. Emergency: 1066, Police Control: 100"
        if "festival" in query:
            return "Bonalu Annual Festival - Celebrated across historic temples"
        if "day trip" in query:
            return "Ananthagiri Hills - 75 km drive scenic nature trails"
        if "attraction" in query:
            return "Golconda Fort: Historic fortress acoustics - Rs 25 entry"
        return "Hyderabadi Dum Biryani and Irani Chai"

    researcher = ParallelResearcher(max_workers=5, search_fn=mock_grounded_search)
    guide = researcher.gather_parallel_city_guide(city="Hyderabad")

    # 1. Emergency info grounding
    assert guide.emergency_info is not None
    assert guide.emergency_info.nearest_hospital is not None
    assert "Apollo" in guide.emergency_info.nearest_hospital.name or "Hospital" in guide.emergency_info.nearest_hospital.name
    assert guide.emergency_info.grounded is True

    # 2. Events grounding
    assert guide.events_grounded is True
    assert len(guide.local_events) >= 1
    assert any("Bonalu" in e.name for e in guide.local_events)

    # 3. Day trips grounding
    assert len(guide.nearby_day_trips) >= 1
    assert any("Ananthagiri" in d.name for d in guide.nearby_day_trips)


def test_parallel_city_research_tool_execution():
    """
    Verify ParallelCityResearchTool produces valid schema-compliant CityGuide JSON.
    """
    tool = ParallelCityResearchTool()
    raw_res = tool._run(city="Kochi", interests="backwaters, spice market")
    data = json.loads(raw_res)

    assert data["city"] == "Kochi"
    assert "top_attractions" in data
    assert "local_cuisine" in data
    assert "emergency_info" in data
    assert "local_events" in data
