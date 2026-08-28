import time
import json
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()

from trip_planner.api.app import app

def run_verification():
    client = TestClient(app)
    
    print("=== STEP 1: Live Trip Planning Request for Vijayawada ===")
    plan_payload = {
        "origin": "Hyderabad",
        "cities": "Vijayawada",
        "interests": "food, biryani, temples, shopping",
        "trip_length": 3,
        "budget": 15000,
        "currency": "INR",
        "travel_mode": "domestic"
    }
    
    start_time = time.time()
    resp = client.post("/api/plan-trip", json=plan_payload)
    print(f"POST /api/plan-trip status: {resp.status_code}")
    assert resp.status_code == 200, f"Plan trip failed: {resp.text}"
    
    init_data = resp.json()
    trip_job_id = init_data["job_id"]
    print(f"Trip Job ID: {trip_job_id}")
    
    # Poll for completion
    while True:
        status_res = client.get(f"/api/status/{trip_job_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        status = status_data["status"]
        elapsed = time.time() - start_time
        print(f"[{elapsed:.1f}s] Trip Job Status: {status}")
        
        if status == "complete":
            trip_result = status_data["result"]
            print("\nTrip Plan Completed Successfully!")
            print(f"Destination: {trip_result.get('destination_city')}, {trip_result.get('destination_country')}")
            print(f"Total Cost: ₹{trip_result.get('total_estimated_cost')}")
            break
        elif status == "failed":
            print(f"Trip planning failed: {status_data.get('error')}")
            return
        
        time.sleep(4)
        
    trip_elapsed = time.time() - start_time
    print(f"Total Trip Planning Elapsed Time: {trip_elapsed:.2f}s")
    
    print("\n=== STEP 2: Live Destination Question against Vijayawada Job ===")
    question_text = "Where can I find good biryani in Vijayawada, and is there a good shopping mall with a cinema?"
    qa_payload = {
        "job_id": trip_job_id,
        "question": question_text
    }
    print(f"Question: \"{question_text}\"")
    
    qa_start_time = time.time()
    qa_resp = client.post("/api/ask-question", json=qa_payload)
    print(f"POST /api/ask-question status: {qa_resp.status_code}")
    assert qa_resp.status_code == 200, f"Ask question failed: {qa_resp.text}"
    
    qa_init_data = qa_resp.json()
    qa_job_id = qa_init_data["job_id"]
    print(f"Q&A Job ID: {qa_job_id}")
    
    # Poll for Q&A completion
    qa_result = None
    while True:
        status_res = client.get(f"/api/status/{qa_job_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        status = status_data["status"]
        elapsed = time.time() - qa_start_time
        print(f"[{elapsed:.1f}s] Q&A Job Status: {status}")
        
        if status == "complete":
            qa_result = status_data["result"]
            break
        elif status == "failed":
            print(f"Q&A Job failed: {status_data.get('error')}")
            return
            
        time.sleep(3)
        
    qa_elapsed = time.time() - qa_start_time
    print(f"\nTotal Q&A Elapsed Time: {qa_elapsed:.2f}s")
    print(f"Actual Q&A Job ID: {qa_job_id}")
    print("\n--- ACTUAL Q&A ANSWER ---")
    if isinstance(qa_result, dict):
        print(qa_result.get("answer"))
        if qa_result.get("sources"):
            print("\nSources surfaced:")
            for s in qa_result["sources"]:
                print(f" - {s}")
    else:
        print(qa_result)
    print("-------------------------\n")

if __name__ == "__main__":
    run_verification()
