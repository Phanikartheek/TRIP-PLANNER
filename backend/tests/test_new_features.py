from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from trip_planner.api import db
from trip_planner.api.app import app, check_and_send_reminders

client = TestClient(app)


def test_checklist_patch_and_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    1. Unit test: checklist PATCH updates the correct item, leaves others unchanged, persists correctly.
    """
    db_file = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_file)
    db.init_db(db_path=db_file)
    job_id = "test-checklist-job"
    db.create_job(job_id, "plan", status="pending", db_path=db_file)

    mock_result = {
        "destination_city": "Manali",
        "packing_suggestions": ["Thermal wear", "Waterproof boots", "Camera"],
    }
    db.update_job(job_id, status="complete", result=mock_result, db_path=db_file)

    # 1. Verify initial GET checklist
    resp = client.get(f"/api/trip/{job_id}/checklist")
    assert resp.status_code == 200
    items = resp.json()["checklist"]
    assert len(items) == 3
    assert all(not item["checked"] for item in items)

    # 2. Patch "Waterproof boots" to checked = True
    patch_resp = client.patch(
        f"/api/trip/{job_id}/checklist",
        json={"item": "Waterproof boots", "checked": True},
    )
    assert patch_resp.status_code == 200
    patched_items = patch_resp.json()["checklist"]

    boots_item = next(i for i in patched_items if i["item"] == "Waterproof boots")
    thermal_item = next(i for i in patched_items if i["item"] == "Thermal wear")
    camera_item = next(i for i in patched_items if i["item"] == "Camera")

    assert boots_item["checked"] is True
    assert thermal_item["checked"] is False
    assert camera_item["checked"] is False

    # 3. Verify persistence via GET
    get_resp = client.get(f"/api/trip/{job_id}/checklist")
    assert get_resp.status_code == 200
    persisted_items = get_resp.json()["checklist"]
    assert next(i for i in persisted_items if i["item"] == "Waterproof boots")["checked"] is True


def test_reminders_and_idempotency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    2. Unit test: check_and_send_reminders() - create job with travel_date = tomorrow and reminder_sent = False,
       call function directly, confirm email sent/logged and reminder_sent flips to True.
       Confirm idempotency when called twice.
    """
    db_file = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_file)
    db.init_db(db_path=db_file)
    job_id = "test-reminder-job"
    tomorrow_str = (datetime.now().date() + timedelta(days=1)).isoformat()

    db.create_job(job_id, "plan", status="pending", user_email="traveler@example.com", travel_date=tomorrow_str, db_path=db_file)
    mock_result = {
        "destination_city": "Udaipur",
        "trip_length_days": 3,
    }
    db.update_job(job_id, status="complete", result=mock_result, db_path=db_file)

    # Confirm initial reminder_sent is False
    job_rec = db.get_job(job_id, db_path=db_file)
    assert job_rec["reminder_sent"] is False

    # Call check_and_send_reminders directly
    processed = check_and_send_reminders(db_path=db_file)
    assert job_id in processed

    # Confirm reminder_sent flipped to True in DB
    updated_job = db.get_job(job_id, db_path=db_file)
    assert updated_job["reminder_sent"] is True

    # Call second time to test idempotency
    second_processed = check_and_send_reminders(db_path=db_file)
    assert job_id not in second_processed


def test_recommendations_endpoint_privacy_and_graceful_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    3. Unit test: recommendations endpoint - excludes queried job itself, excludes private fields,
       and returns fewer than 3 gracefully when insufficient data exists (doesn't fabricate).
    """
    db_file = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_file)
    db.init_db(db_path=db_file)

    # Job A: Main queried job
    job_a_result = {
        "destination_city": "Kochi",
        "destination_country": "India",
        "trip_length_days": 2,
        "total_estimated_cost": 15000.0,
        "currency": "INR",
        "interests": "backwaters, food",
        "days": [{"day_number": 1, "theme": "Fort Kochi Heritage"}],
    }
    db.create_job("job-rec-a", "plan", status="pending", user_email="secret_a@example.com", db_path=db_file)
    db.update_job("job-rec-a", status="complete", result=job_a_result, qa_history=[{"question": "Secret QA"}], db_path=db_file)

    # Job B: Matching job 1
    job_b_result = {
        "destination_city": "Alleppey",
        "destination_country": "India",
        "trip_length_days": 2,
        "total_estimated_cost": 12000.0,
        "currency": "INR",
        "interests": "backwaters, houseboats",
        "days": [{"day_number": 1, "theme": "Backwater Houseboat"}],
    }
    db.create_job("job-rec-b", "plan", status="pending", user_email="secret_b@example.com", db_path=db_file)
    db.update_job("job-rec-b", status="complete", result=job_b_result, db_path=db_file)

    # Fetch recommendations for Job A
    resp = client.get("/api/trip/job-rec-a/recommendations")
    assert resp.status_code == 200
    data = resp.json()

    assert "recommendations" in data
    recs = data["recommendations"]

    # Must return at most available matches (1 item here, not fabricated 3)
    assert len(recs) == 1

    rec_item = recs[0]
    # Confirm it is Job B and NOT Job A itself
    assert rec_item["job_id"] == "job-rec-b"
    assert rec_item["destination_city"] == "Alleppey"

    # Confirm EXCLUSION of private fields
    assert "user_email" not in rec_item
    assert "qa_history" not in rec_item
    assert "packing_suggestions" not in rec_item
