"""
Unit tests for the public shareable read-only trip endpoint GET /api/trip/{job_id}/share.
"""

from fastapi.testclient import TestClient
from trip_planner.api import db
from trip_planner.api.app import app

client = TestClient(app)


def test_get_shareable_trip_returns_404_for_nonexistent_job():
    res = client.get("/api/trip/non-existent-share-uuid/share")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_shareable_trip_returns_404_for_incomplete_job():
    job_id = "pending-share-job-uuid"
    db.create_job(job_id=job_id, job_type="plan", status="pending")
    res = client.get(f"/api/trip/{job_id}/share")
    assert res.status_code == 404
    assert "not complete" in res.json()["detail"].lower()


def test_get_shareable_trip_returns_clean_read_only_itinerary():
    job_id = "complete-share-job-uuid"
    db.create_job(job_id=job_id, job_type="plan", status="complete", user_email="private_user@example.com")
    
    itinerary_data = {
        "destination_city": "Udaipur",
        "destination_country": "India",
        "trip_length_days": 2,
        "currency": "INR",
        "total_estimated_cost": 12000.0,
        "days": [
            {
                "day_number": 1,
                "theme": "Palaces & Lake Pichola",
                "morning": "Visit City Palace complex",
                "afternoon": "Lunch at Jagat Niwas",
                "evening": "Sunset boat ride on Lake Pichola",
                "estimated_cost": 6000.0,
                "cost_breakdown": [
                    {"item": "Palace entry", "amount": 1000.0},
                    {"item": "Boat ride", "amount": 2000.0},
                    {"item": "Dining", "amount": 3000.0}
                ]
            }
        ],
        "packing_suggestions": ["Sunglasses", "Sunscreen"],
        "local_transport_advice": ["Auto rickshaws for narrow lanes"]
    }
    
    db.update_job(
        job_id=job_id,
        status="complete",
        result=itinerary_data,
        qa_history=[{"question": "Where to stay?", "answer": "Taj Lake Palace"}]
    )

    res = client.get(f"/api/trip/{job_id}/share")
    assert res.status_code == 200
    data = res.json()

    # Assert expected TripItinerary structure
    assert data["destination_city"] == "Udaipur"
    assert data["destination_country"] == "India"
    assert data["trip_length_days"] == 2
    assert data["total_estimated_cost"] == 12000.0
    assert len(data["days"]) == 1
    assert data["days"][0]["day_number"] == 1

    # Assert strict privacy & metadata stripping (NO user_email, NO qa_history)
    assert "user_email" not in data, "PRIVACY VIOLATION: user_email exposed in public share endpoint!"
    assert "qa_history" not in data, "PRIVACY VIOLATION: qa_history exposed in public share endpoint!"
    assert "job_id" not in data, "Metadata field job_id should not be in public payload"
    assert "created_at" not in data, "Metadata field created_at should not be in public payload"
