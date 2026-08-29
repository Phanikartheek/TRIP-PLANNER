"""
Unit tests for Cost Breakdown schema and arithmetic reconciliation validator.
"""

from trip_planner.schemas.models import CostItem, ItineraryDay, TripItinerary


def test_cost_breakdown_schema_and_reconciliation():
    day1 = ItineraryDay(
        day_number=1,
        theme="Temple & Food Tour",
        morning="Visit Kanaka Durga Temple",
        afternoon="Lunch at Babai Hotel",
        evening="Sunset at Prakasam Barrage",
        estimated_cost=0.0,  # Will be reconciled from cost_breakdown sum
        cost_breakdown=[
            CostItem(item="Temple VIP Darshan", amount=500.0),
            CostItem(item="Lunch at Babai Hotel", amount=350.0),
            CostItem(item="Local Cab fare", amount=650.0),
        ],
    )

    day2 = ItineraryDay(
        day_number=2,
        theme="Heritage Site",
        morning="Kondapalli Fort tour",
        afternoon="Toy shopping",
        evening="Return transit",
        estimated_cost=0.0,
        cost_breakdown=[
            CostItem(item="Fort entry & guide", amount=200.0),
            CostItem(item="Kondapalli toys", amount=800.0),
            CostItem(item="Auto fare", amount=500.0),
        ],
    )

    itinerary = TripItinerary(
        destination_city="Vijayawada",
        destination_country="India",
        trip_length_days=2,
        currency="INR",
        total_estimated_cost=0.0,  # Reconciled automatically
        days=[day1, day2],
        packing_suggestions=["Sunhat", "Water bottle"],
        local_transport_advice=["Auto rickshaws"],
    )

    # Reconciled daily costs: Day 1 = 500+350+650 = 1500; Day 2 = 200+800+500 = 1500
    assert itinerary.days[0].estimated_cost == 1500.0
    assert itinerary.days[1].estimated_cost == 1500.0
    # Reconciled total itinerary cost = 1500 + 1500 = 3000.0
    assert itinerary.total_estimated_cost == 3000.0
