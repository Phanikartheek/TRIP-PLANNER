"""
Unit tests for PDF export endpoint and ReportLab PDF document generation.
"""

from fastapi.testclient import TestClient
from trip_planner.api import db
from trip_planner.api.app import app


def test_pdf_export_endpoint(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_pdf.db"
    db.init_db(db_path=test_db_path)
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", test_db_path)

    sample_itinerary = {
        "destination_city": "Visakhapatnam",
        "destination_country": "India",
        "trip_length_days": 2,
        "currency": "INR",
        "total_estimated_cost": 8500.0,
        "days": [
            {
                "day_number": 1,
                "theme": "Coastal Exploration & Submarine",
                "morning": "Visit INS Kurusura Submarine Museum at RK Beach",
                "afternoon": "Lunch at Kamat Restaurant; visit Kailasagiri Hilltop",
                "evening": "Sunset stroll at Rushikonda Beach",
                "estimated_cost": 4500.0,
                "cost_breakdown": [
                    {"item": "Submarine ticket", "amount": 200.0},
                    {"item": "Lunch at Kamat", "amount": 800.0},
                    {"item": "Ropeway & cab", "amount": 3500.0},
                ],
            },
            {
                "day_number": 2,
                "theme": "Araku Valley Day Trip",
                "morning": "Vistadome train ride to Borra Caves",
                "afternoon": "Explore coffee plantations & Katiki Waterfalls",
                "evening": "Return train to Vizag city",
                "estimated_cost": 4000.0,
                "cost_breakdown": [
                    {"item": "Train tickets", "amount": 1500.0},
                    {"item": "Cave entry & guide", "amount": 500.0},
                    {"item": "Bamboo chicken lunch & cab", "amount": 2000.0},
                ],
            },
        ],
        "packing_suggestions": ["Cotton clothes", "Sunscreen", "Comfortable walking shoes"],
        "local_transport_advice": ["Vistadome train to Araku", "Prepaid auto rickshaws in Vizag"],
    }

    job_id = "test-pdf-job-12345"
    db.create_job(job_id=job_id, job_type="plan", status="complete", db_path=test_db_path)
    db.update_job(job_id=job_id, status="complete", result=sample_itinerary, db_path=test_db_path)

    client = TestClient(app)
    response = client.get(f"/api/trip/{job_id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 1000
