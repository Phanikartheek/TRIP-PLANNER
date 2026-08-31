"""
Unit tests for Emergency Info Card & Local Phrasebook features.
"""

from trip_planner.schemas.models import (
    EmergencyInfo,
    EmergencyLocation,
    PhrasebookEntry,
    TripItinerary,
    get_regional_language_for_city,
)


def test_emergency_info_schema_validation():
    """
    1. Unit test: emergency_info schema validation, including grounded=True and grounded=False fallback case.
    """
    # Grounded case with real search results
    em_grounded = EmergencyInfo(
        national_emergency_number="112",
        nearest_hospital=EmergencyLocation(name="Medical Trust Hospital", area="MG Road, Kochi"),
        nearest_police_station=EmergencyLocation(name="Central Police Station", area="Ernakulam, Kochi"),
        grounded=True,
    )
    assert em_grounded.national_emergency_number == "112"
    assert em_grounded.nearest_hospital is not None
    assert em_grounded.nearest_hospital.name == "Medical Trust Hospital"
    assert em_grounded.grounded is True

    # Fallback case with grounded=False
    em_fallback = EmergencyInfo(
        national_emergency_number="112",
        nearest_hospital=None,
        nearest_police_station=None,
        grounded=False,
    )
    assert em_fallback.national_emergency_number == "112"
    assert em_fallback.nearest_hospital is None
    assert em_fallback.nearest_police_station is None
    assert em_fallback.grounded is False

    # Validate TripItinerary embedding
    itinerary_data = {
        "destination_city": "Kochi",
        "destination_country": "India",
        "trip_length_days": 2,
        "total_estimated_cost": 10000.0,
        "currency": "INR",
        "days": [
            {
                "day_number": 1,
                "theme": "Fort Kochi Walk",
                "morning": "Walk around Chinese Fishing Nets",
                "afternoon": "Lunch at Kashi Art Cafe",
                "evening": "Kathakali Performance",
                "estimated_cost": 5000.0,
            },
            {
                "day_number": 2,
                "theme": "Mattancherry & Spice Market",
                "morning": "Mattancherry Palace",
                "afternoon": "Jew Town & Spices",
                "evening": "Sunset Cruise",
                "estimated_cost": 5000.0,
            },
        ],
        "packing_suggestions": ["Cotton clothes", "Sunscreen"],
        "emergency_info": em_grounded.model_dump(),
    }
    itinerary = TripItinerary(**itinerary_data)
    assert itinerary.emergency_info is not None
    assert itinerary.emergency_info.grounded is True
    assert itinerary.emergency_info.nearest_hospital.name == "Medical Trust Hospital"


def test_local_phrasebook_schema_validation():
    """
    2. Unit test: local_phrasebook schema validation (correct structure, minimum phrase count).
    """
    phrases = [
        PhrasebookEntry(phrase_english="Hello", phrase_local="నమస్కారం", pronunciation="Namaskaram"),
        PhrasebookEntry(phrase_english="Thank you", phrase_local="ధన్యవాదాలు", pronunciation="Dhanyavaadalu"),
        PhrasebookEntry(phrase_english="How much does this cost?", phrase_local="దీని ధర ఎంత?", pronunciation="Deeni dhara entha?"),
        PhrasebookEntry(phrase_english="Where is the bathroom?", phrase_local="వాష్‌రూమ్ ఎక్కడ ఉంది?", pronunciation="Washroom ekkada undhi?"),
        PhrasebookEntry(phrase_english="I need help", phrase_local="నాకు సహాయం కావాలి", pronunciation="Naaku sahaayam kaavali"),
        PhrasebookEntry(phrase_english="Water please", phrase_local="మంచినీళ్ళు ఇవ్వండి", pronunciation="Manchineellu ivvandi"),
        PhrasebookEntry(phrase_english="Stop here", phrase_local="ఇక్కడ ఆపండి", pronunciation="Ikkada aapandi"),
        PhrasebookEntry(phrase_english="Delicious food", phrase_local="చాలా బాగుంది", pronunciation="Chaala baagundhi"),
    ]

    assert len(phrases) >= 8
    for p in phrases:
        assert len(p.phrase_english) > 0
        assert len(p.phrase_local) > 0
        assert len(p.pronunciation) > 0

    itinerary_data = {
        "destination_city": "Vijayawada",
        "destination_country": "India",
        "trip_length_days": 1,
        "total_estimated_cost": 4000.0,
        "currency": "INR",
        "days": [
            {
                "day_number": 1,
                "theme": "Kanaka Durga Temple",
                "morning": "Temple visit",
                "afternoon": "Lunch at Babai Hotel",
                "evening": "Prakasam Barrage walk",
                "estimated_cost": 4000.0,
            }
        ],
        "packing_suggestions": ["Modest temple wear"],
        "local_phrasebook": [p.model_dump() for p in phrases],
    }
    itinerary = TripItinerary(**itinerary_data)
    assert itinerary.local_phrasebook is not None
    assert len(itinerary.local_phrasebook) == 8
    assert itinerary.local_phrasebook[0].phrase_local == "నమస్కారం"


def test_regional_language_selection_logic():
    """
    3. Unit test: confirm get_regional_language_for_city picks sensible regional language
       for known cities (e.g. Kochi -> Malayalam, Vijayawada -> Telugu, Mysuru -> Kannada, Jaipur -> Hindi, Kolkata -> Bengali).
    """
    assert get_regional_language_for_city("Kochi") == "Malayalam"
    assert get_regional_language_for_city("Cochin") == "Malayalam"
    assert get_regional_language_for_city("Vijayawada") == "Telugu"
    assert get_regional_language_for_city("Visakhapatnam") == "Telugu"
    assert get_regional_language_for_city("Mysuru") == "Kannada"
    assert get_regional_language_for_city("Bengaluru") == "Kannada"
    assert get_regional_language_for_city("Jaipur") == "Hindi"
    assert get_regional_language_for_city("Udaipur") == "Hindi"
    assert get_regional_language_for_city("Kolkata") == "Bengali"
    assert get_regional_language_for_city("Chennai") == "Tamil"
    assert get_regional_language_for_city("Mumbai") == "Marathi"
