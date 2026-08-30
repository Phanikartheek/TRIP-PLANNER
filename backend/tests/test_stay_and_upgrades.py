"""
Unit tests for recommended_stay (AccommodationOption) and budget_upgrade_insights (SmartBudgetUpgrade) schema contracts.
"""

import pytest
from pydantic import ValidationError
from trip_planner.schemas.models import AccommodationOption, SmartBudgetUpgrade, TripItinerary


def test_accommodation_option_valid_payload():
    """Verify AccommodationOption accepts valid payload with all required fields."""
    stay = AccommodationOption(
        name="Hotel Menaka",
        category="Budget Stay",
        estimated_price_per_night=700.0,
        address_or_area="Near Vijayawada Station",
        why_recommended="Strategic location close to transport hubs at an affordable price.",
    )
    assert stay.name == "Hotel Menaka"
    assert stay.category == "Budget Stay"
    assert stay.estimated_price_per_night == 700.0
    assert stay.address_or_area == "Near Vijayawada Station"
    assert "Strategic location" in stay.why_recommended


def test_accommodation_option_rejects_missing_required_fields():
    """Verify AccommodationOption raises ValidationError when required fields are missing."""
    with pytest.raises(ValidationError):
        AccommodationOption(name="Incomplete Stay")  # Missing price, address, why_recommended

    with pytest.raises(ValidationError):
        AccommodationOption(
            name="No Area Hotel",
            estimated_price_per_night=500.0,
            why_recommended="Good stay",
        )  # Missing address_or_area


def test_smart_budget_upgrade_valid_payload():
    """Verify SmartBudgetUpgrade accepts valid payload and default values."""
    upgrade = SmartBudgetUpgrade(
        extra_amount=2500.0,
        hotel_upgrade="Upgrade to 3-Star Comfort Hotel Sri Lakshmi Vilas",
        dining_upgrade="Premium Andhra thali at Babai Hotel",
        attraction_upgrade="Guided boat tour on Krishna River",
        summary_tip="Adding ₹2,500 unlocks better stay comfort and authentic dining.",
    )
    assert upgrade.extra_amount == 2500.0
    assert "Sri Lakshmi Vilas" in upgrade.hotel_upgrade
    assert "Babai Hotel" in upgrade.dining_upgrade
    assert "Krishna River" in upgrade.attraction_upgrade
    assert "Adding ₹2,500" in upgrade.summary_tip


def test_smart_budget_upgrade_rejects_missing_summary_tip():
    """Verify SmartBudgetUpgrade raises ValidationError when required summary_tip is omitted."""
    with pytest.raises(ValidationError):
        SmartBudgetUpgrade(extra_amount=2000.0)  # Missing summary_tip


def test_trip_itinerary_with_stay_and_upgrades_reconciles_cost():
    """Verify TripItinerary with recommended_stay and budget_upgrade_insights compiles and reconciles cost."""
    itinerary = TripItinerary(
        destination_city="Vijayawada",
        destination_country="India",
        trip_length_days=2,
        total_estimated_cost=9999.0,  # Mismatched total
        days=[
            {
                "day_number": 1,
                "theme": "Temples",
                "morning": "Kanaka Durga",
                "afternoon": "Ghats",
                "evening": "Market",
                "estimated_cost": 980.0,
                "cost_breakdown": [
                    {"item": "Hotel Menaka", "amount": 700.0},
                    {"item": "Auto fare", "amount": 150.0},
                    {"item": "Breakfast", "amount": 50.0},
                    {"item": "Lunch", "amount": 50.0},
                    {"item": "Snacks", "amount": 30.0},
                ],
            },
            {
                "day_number": 2,
                "theme": "Caves",
                "morning": "Undavalli Caves",
                "afternoon": "Lunch",
                "evening": "Return",
                "estimated_cost": 1000.0,
                "cost_breakdown": [
                    {"item": "Auto fare", "amount": 200.0},
                    {"item": "Cave entry", "amount": 10.0},
                    {"item": "Breakfast", "amount": 40.0},
                    {"item": "Lunch: Gongura Mutton", "amount": 150.0},
                    {"item": "Evening snack: Mirchi Bajji", "amount": 30.0},
                    {"item": "Evening tea & souvenir", "amount": 570.0},
                ],
            },
        ],
        packing_suggestions=["Cotton shirt", "Hat"],
        recommended_stay=AccommodationOption(
            name="Hotel Menaka",
            category="Budget Stay",
            estimated_price_per_night=700.0,
            address_or_area="Near Vijayawada Station",
            why_recommended="Affordable and central",
        ),
        budget_upgrade_insights=SmartBudgetUpgrade(
            extra_amount=2500.0,
            summary_tip="Spend ₹2,500 more for 3-star hotel and full Andhra thali.",
        ),
    )

    # Cost reconciliation validator must still calculate total_estimated_cost = 980.0 + 1000.0 = 1980.0
    assert itinerary.total_estimated_cost == 1980.0
    assert itinerary.recommended_stay is not None
    assert itinerary.recommended_stay.name == "Hotel Menaka"
    assert itinerary.budget_upgrade_insights is not None
    assert itinerary.budget_upgrade_insights.extra_amount == 2500.0
