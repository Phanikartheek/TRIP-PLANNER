"""
Real Live End-to-End Verification Script with Real Groq LLM Execution.
Executes genuine POST /api/plan-trip HTTP requests, captures real returned UUID4 job IDs,
polls background CrewAI execution until complete, and verifies logged-in vs anonymous trip privacy isolation.
"""

import json
import threading
import time

import requests
import uvicorn
from dotenv import load_dotenv
from trip_planner.api import db
from trip_planner.api.app import app

load_dotenv()

PORT = 8009
BASE_URL = f"http://127.0.0.1:{PORT}"


def start_server():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def verify_real_live():
    print("=" * 80)
    print("    REAL LIVE VERIFICATION (GENUINE END-TO-END POST /api/plan-trip)")
    print("=" * 80)

    # Launch server in background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Wait for server readiness
    print("Waiting for server startup on port 8009...")
    for _ in range(20):
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=2)
            if r.status_code == 200:
                print(f"✓ Backend server responsive: {r.json()}")
                break
        except Exception:
            time.sleep(0.5)

    user_email = "real_auth_user@example.com"
    session = requests.Session()

    # STEP 1: Magic Link Request
    print("\n--- STEP 1: POST /api/auth/request-login ---")
    res1 = session.post(f"{BASE_URL}/api/auth/request-login", json={"email": user_email})
    print(f"Status Code: {res1.status_code}")
    print(f"Response Body: {res1.json()}")

    # Retrieve generated token from DB
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT token FROM login_tokens WHERE email = ? ORDER BY expires_at DESC LIMIT 1;", (user_email,))
        row = cursor.fetchone()
        assert row is not None, "Login token not found in SQLite DB"
        token = row["token"]

    print(f"✓ Retrieved Login Token: {token}")

    # STEP 2: Verify Token & Get Session Cookie
    print("\n--- STEP 2: GET /api/auth/verify?token=... ---")
    res2 = session.get(f"{BASE_URL}/api/auth/verify?token={token}", allow_redirects=False)
    print(f"Status Code: {res2.status_code} (Redirect -> {res2.headers.get('location')})")
    session_token = res2.cookies.get("session_token") or session.cookies.get("session_token")
    assert session_token is not None, "session_token cookie missing!"
    print(f"✓ Session Cookie: {session_token}")

    # Verify /api/auth/me
    res_me = session.get(f"{BASE_URL}/api/auth/me")
    print(f"GET /api/auth/me Response: {res_me.json()}")
    assert res_me.json()["email"] == user_email

    # STEP 3: REAL Authenticated POST /api/plan-trip
    print("\n--- STEP 3: REAL POST /api/plan-trip (AUTHENTICATED) ---")
    auth_payload = {
        "origin": "Bengaluru",
        "cities": "Goa, Munnar",
        "interests": "beaches, street food, waterfalls",
        "trip_length": 2,
        "budget": 20000,
        "currency": "INR",
        "travel_mode": "domestic",
        "language": "en"
    }

    start_time_auth = time.time()
    res_auth_plan = session.post(f"{BASE_URL}/api/plan-trip", json=auth_payload)
    print(f"HTTP Status Code: {res_auth_plan.status_code}")
    auth_plan_json = res_auth_plan.json()
    print(f"Response Body: {json.dumps(auth_plan_json, indent=2)}")

    auth_job_id = auth_plan_json.get("job_id")
    assert auth_job_id is not None, "job_id is missing!"
    print(f"\nCaptured Genuine Auth UUID4 Job ID: {auth_job_id}")

    # Poll status until complete
    print(f"Polling GET /api/status/{auth_job_id} until completion...")
    auth_job_status = "pending"
    auth_result = None
    poll_count = 0

    while auth_job_status in ("pending", "running"):
        time.sleep(3)
        poll_count += 1
        st_res = session.get(f"{BASE_URL}/api/status/{auth_job_id}")
        st_json = st_res.json()
        auth_job_status = st_json.get("status")
        elapsed = round(time.time() - start_time_auth, 1)
        print(f"  [Poll #{poll_count} | Elapsed: {elapsed}s] Status: {auth_job_status}")
        if auth_job_status == "complete":
            auth_result = st_json.get("result")
            break
        elif auth_job_status == "failed":
            raise RuntimeError(f"Authenticed job failed: {st_json.get('error')}")

    total_auth_elapsed = round(time.time() - start_time_auth, 1)
    print(f"✓ Authenticated Job Complete in {total_auth_elapsed} seconds!")
    print(f"  Destination City Chosen by CrewAI: {auth_result.get('destination_city')}")
    print(f"  Total Estimated Cost: {auth_result.get('currency')} {auth_result.get('total_estimated_cost')}")

    # STEP 4: GET /api/my-trips Verification
    print("\n--- STEP 4: GET /api/my-trips (AUTHENTICATED USER ISOLATION CHECK) ---")
    res_my_trips = session.get(f"{BASE_URL}/api/my-trips")
    print(f"HTTP Status Code: {res_my_trips.status_code}")
    my_trips_data = res_my_trips.json()
    print(f"Response Body:\n{json.dumps(my_trips_data, indent=2)}")

    user_trips = my_trips_data.get("trips", [])
    user_job_ids = [t["job_id"] for t in user_trips]
    assert auth_job_id in user_job_ids, f"Expected real job_id {auth_job_id} in my-trips!"

    found_job = next(t for t in user_trips if t["job_id"] == auth_job_id)
    assert found_job["user_email"] == user_email
    print(f"✓ Real UUID4 Job {auth_job_id} correctly associated with user_email '{user_email}' via API endpoint!")

    # STEP 5: REAL Anonymous POST /api/plan-trip (NO SESSION COOKIE)
    print("\n--- STEP 5: REAL POST /api/plan-trip (ANONYMOUS / NO COOKIE) ---")
    anon_session = requests.Session()  # Fresh session without any cookies

    anon_payload = {
        "origin": "Hyderabad",
        "cities": "Vijayawada, Vizag",
        "interests": "temples, food",
        "trip_length": 2,
        "budget": 15000,
        "currency": "INR",
        "travel_mode": "domestic",
        "language": "en"
    }

    start_time_anon = time.time()
    res_anon_plan = anon_session.post(f"{BASE_URL}/api/plan-trip", json=anon_payload)
    print(f"HTTP Status Code: {res_anon_plan.status_code}")
    anon_plan_json = res_anon_plan.json()
    print(f"Response Body: {json.dumps(anon_plan_json, indent=2)}")

    anon_job_id = anon_plan_json.get("job_id")
    assert anon_job_id is not None, "Anonymous job_id missing!"
    print(f"\nCaptured Genuine Anonymous UUID4 Job ID: {anon_job_id}")

    # Poll status until complete
    print(f"Polling GET /api/status/{anon_job_id} until completion...")
    anon_job_status = "pending"
    poll_count_anon = 0

    while anon_job_status in ("pending", "running"):
        time.sleep(3)
        poll_count_anon += 1
        st_res = anon_session.get(f"{BASE_URL}/api/status/{anon_job_id}")
        st_json = st_res.json()
        anon_job_status = st_json.get("status")
        elapsed = round(time.time() - start_time_anon, 1)
        print(f"  [Poll #{poll_count_anon} | Elapsed: {elapsed}s] Status: {anon_job_status}")
        if anon_job_status == "complete":
            break
        elif anon_job_status == "failed":
            raise RuntimeError(f"Anonymous job failed: {st_json.get('error')}")

    total_anon_elapsed = round(time.time() - start_time_anon, 1)
    print(f"✓ Anonymous Job Complete in {total_anon_elapsed} seconds!")

    # Verify Anonymous Job is NOT visible in Authenticated User's /api/my-trips
    print("\n--- PRIVACY VERIFICATION: GET /api/my-trips WITH AUTH COOKIE ---")
    res_my_trips_check = session.get(f"{BASE_URL}/api/my-trips")
    trips_check_ids = [t["job_id"] for t in res_my_trips_check.json().get("trips", [])]

    print(f"Authenticated User's Trips in DB: {trips_check_ids}")
    print(f"Anonymous Job ID: {anon_job_id}")
    assert anon_job_id not in trips_check_ids, f"PRIVACY VIOLATION: Anonymous job {anon_job_id} appeared in user's my-trips!"
    print("✓ PRIVACY ISOLATION VERIFIED: Anonymous job is strictly isolated and NOT returned in user's /api/my-trips!")

    print("\n" + "=" * 80)
    print("      REAL LIVE VERIFICATION COMPLETED WITH 100% SUCCESS")
    print("=" * 80)


if __name__ == "__main__":
    verify_real_live()
