import pytest
from trip_planner.api.app import (
    calculate_distance_km,
    get_city_coordinates,
    optimize_city_route,
    reconcile_multi_city_itinerary,
)


def test_calculate_distance_km():
    """
    Verifies Haversine distance calculation between known coordinates.
    Vijayawada (16.5062, 80.6480) to Guntur (16.3067, 80.4365) is ~30-35 km.
    """
    c_vijayawada = get_city_coordinates("Vijayawada")
    c_guntur = get_city_coordinates("Guntur")
    assert c_vijayawada is not None
    assert c_guntur is not None

    dist = calculate_distance_km(c_vijayawada, c_guntur)
    assert 25.0 <= dist <= 40.0


def test_route_optimizer_sequences_vijayawada_guntur_nellore_tirupati():
    """
    CRITICAL REAL-WORLD TEST:
    Starting from Vijayawada, visiting [Nellore, Tirupati, Guntur].
    Unoptimized random order would go south to Nellore (280km), backtrack north to Guntur (250km),
    then back south to Tirupati (380km).
    The optimizer MUST sequence it strictly as:
    Guntur (35km nearest) -> Nellore (250km) -> Tirupati (135km)!
    """
    origin = "Vijayawada"
    candidate_cities = ["Nellore", "Tirupati", "Guntur"]

    optimized = optimize_city_route(origin, candidate_cities)
    assert optimized == ["Guntur", "Nellore", "Tirupati"]


def test_route_optimizer_eliminates_backtracking_distance():
    """
    Verifies that the optimized route saves hundreds of kilometers of unnecessary travel.
    """
    origin = "Vijayawada"
    c_vijayawada = get_city_coordinates(origin)
    c_guntur = get_city_coordinates("Guntur")
    c_nellore = get_city_coordinates("Nellore")
    c_tirupati = get_city_coordinates("Tirupati")

    # Unoptimized: Vijayawada -> Nellore -> Guntur -> Tirupati
    dist_unoptimized = (
        calculate_distance_km(c_vijayawada, c_nellore)
        + calculate_distance_km(c_nellore, c_guntur)
        + calculate_distance_km(c_guntur, c_tirupati)
    )

    # Optimized: Vijayawada -> Guntur -> Nellore -> Tirupati
    dist_optimized = (
        calculate_distance_km(c_vijayawada, c_guntur)
        + calculate_distance_km(c_guntur, c_nellore)
        + calculate_distance_km(c_nellore, c_tirupati)
    )

    savings = dist_unoptimized - dist_optimized
    assert dist_optimized < 465.0
    assert dist_unoptimized > 700.0
    assert savings > 280.0  # Saves over 300 km straight-line (~450 km rail/road)!


def test_route_optimizer_from_hyderabad_to_rayalaseema():
    """
    Starting from Hyderabad to Kurnool and Tirupati:
    Kurnool (~180km) is much closer than Tirupati (~450km).
    Must visit Kurnool first before heading to Tirupati.
    """
    origin = "Hyderabad"
    candidates = ["Tirupati", "Kurnool"]
    optimized = optimize_city_route(origin, candidates)
    assert optimized == ["Kurnool", "Tirupati"]


def test_reconcile_multi_city_itinerary_attaches_route_analysis():
    """
    Verifies that reconcile_multi_city_itinerary attaches route_analysis
    with start_hub, legs, distance_saved_km, and proximity badges.
    """
    mock_itinerary = {
        "destination_city": "Vijayawada",
        "total_estimated_cost": 30000.0,
        "days": [
            {
                "day_number": 1,
                "theme": "Guntur Spice & Amaravati Heritage",
                "morning": "Morning exploration in Guntur Amaravati",
                "city": "Guntur",
            },
            {
                "day_number": 2,
                "theme": "Nellore Beach & Nelapattu",
                "morning": "Mypadu beach in Nellore",
                "city": "Nellore",
            },
            {
                "day_number": 3,
                "theme": "Tirupati Temple Darshan",
                "morning": "Tirumala Venkateswara in Tirupati",
                "city": "Tirupati",
            },
        ],
    }

    reconcile_multi_city_itinerary(
        mock_itinerary,
        raw_cities=["Nellore", "Tirupati", "Guntur"],
        origin_name="Vijayawada",
        budget_val=30000.0,
    )

    assert "route_analysis" in mock_itinerary
    analysis = mock_itinerary["route_analysis"]
    assert analysis["start_hub"] == "Vijayawada"
    assert analysis["optimized_sequence"] == ["Vijayawada", "Guntur", "Nellore", "Tirupati"]
    assert len(analysis["legs"]) == 3
    assert analysis["distance_saved_km"] >= 280.0
    assert analysis["legs"][0]["proximity_badge"] == "Nearest Adjacent First ✅"
    assert analysis["legs"][-1]["proximity_badge"] == "Farthest Final Stop 🏁"

