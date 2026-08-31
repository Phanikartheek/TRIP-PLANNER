"""
Unit tests for Local Festivals & Events Calendar, Etiquette Guide, and Nearby Day Trips features.
"""

from trip_planner.schemas.models import (
    EtiquetteItem,
    LocalEvent,
    NearbyDayTrip,
    TripItinerary,
)


def test_local_events_schema_validation():
    """
    1. Unit test: local_events schema validation including the events_grounded=False fallback case.
    """
    # Grounded case with real search results
    events_grounded = [
        LocalEvent(
            name="Mysore Dasara",
            date_or_period="September / October (Vijayadashami)",
            description="10-day grand festival featuring illuminated Mysore Palace and royal elephant procession.",
        ),
        LocalEvent(
            name="Winter Festival",
            date_or_period="December 29 - 31",
            description="Cultural dance and music performances held at Mount Abu.",
        ),
    ]

    itinerary_grounded = TripItinerary(
        destination_city="Mysuru",
        destination_country="India",
        trip_length_days=2,
        total_estimated_cost=12000.0,
        currency="INR",
        days=[],
        packing_suggestions=["Traditional wear", "Camera"],
        local_events=events_grounded,
        events_grounded=True,
    )
    assert itinerary_grounded.local_events is not None
    assert len(itinerary_grounded.local_events) == 2
    assert itinerary_grounded.events_grounded is True
    assert itinerary_grounded.local_events[0].name == "Mysore Dasara"

    # Fallback case with events_grounded=False
    itinerary_fallback = TripItinerary(
        destination_city="Unknown Remote Village",
        destination_country="India",
        trip_length_days=1,
        total_estimated_cost=3000.0,
        currency="INR",
        days=[],
        packing_suggestions=["Water bottle"],
        local_events=None,
        events_grounded=False,
    )
    assert itinerary_fallback.local_events is None
    assert itinerary_fallback.events_grounded is False


def test_local_etiquette_schema_validation():
    """
    2. Unit test: local_etiquette schema validation (minimum item count 5+, correct structure).
    """
    etiquette_items = [
        EtiquetteItem(
            category="Temple Dress Code",
            advice="Wear traditional modest clothing. Dhotis/mundus for men and sarees/salwars for women are strictly mandated at traditional South Indian temples.",
        ),
        EtiquetteItem(
            category="Footwear Removal",
            advice="Always remove shoes and socks before entering temple premises and local homes.",
        ),
        EtiquetteItem(
            category="Photography Restrictions",
            advice="Photography is strictly prohibited inside inner temple sanctums (Garbhagriha).",
        ),
        EtiquetteItem(
            category="Tipping Norms",
            advice="Tipping 7-10% at sit-down restaurants is customary; small tips (₹20-50) for hotel porters.",
        ),
        EtiquetteItem(
            category="Greeting Custom",
            advice="Greet elders and locals with folded hands saying 'Namaste' or 'Namaskara'.",
        ),
    ]

    assert len(etiquette_items) >= 5

    itinerary = TripItinerary(
        destination_city="Mysuru",
        destination_country="India",
        trip_length_days=2,
        total_estimated_cost=10000.0,
        currency="INR",
        days=[],
        packing_suggestions=["Modest attire"],
        local_etiquette=etiquette_items,
    )
    assert itinerary.local_etiquette is not None
    assert len(itinerary.local_etiquette) >= 5
    assert itinerary.local_etiquette[0].category == "Temple Dress Code"


def test_nearby_day_trips_schema_validation():
    """
    3. Unit test: nearby_day_trips schema validation, including null-when-nothing-found case.
    """
    day_trips = [
        NearbyDayTrip(
            name="Seringapatam (Srirangapatna)",
            distance_from_destination="15 km (30 mins drive)",
            why_visit="Island fortress town of Tipu Sultan featuring Daria Daulat Palace and Ranganathaswamy Temple.",
        ),
        NearbyDayTrip(
            name="Somnathpur Keshava Temple",
            distance_from_destination="35 km (1 hr drive)",
            why_visit="Stunning 13th-century Hoysala star-shaped temple with intricate stone carvings.",
        ),
    ]

    itinerary = TripItinerary(
        destination_city="Mysuru",
        destination_country="India",
        trip_length_days=2,
        total_estimated_cost=10000.0,
        currency="INR",
        days=[],
        packing_suggestions=["Walking shoes"],
        nearby_day_trips=day_trips,
    )
    assert itinerary.nearby_day_trips is not None
    assert len(itinerary.nearby_day_trips) == 2
    assert itinerary.nearby_day_trips[0].name == "Seringapatam (Srirangapatna)"

    # Fallback null case
    itinerary_null = TripItinerary(
        destination_city="Isolated Island",
        destination_country="India",
        trip_length_days=1,
        total_estimated_cost=2000.0,
        currency="INR",
        days=[],
        packing_suggestions=["Water bottle"],
        nearby_day_trips=None,
    )
    assert itinerary_null.nearby_day_trips is None
