"""
Single-Script Live Verification 1 — Group Cost Splitting
Submits request with travelers: 4 and budget: 20000, polls to completion in a single blocking loop,
and confirms cost_per_person == total_estimated_cost / 4.
"""

import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

API_BASE = "http://127.0.0.1:8000"

payload = {
    "origin": "Bengaluru",
    "cities": "Kochi",
    "interests": "backwaters, food, culture",
    "trip_length": 2,
    "budget": 20000.0,
    "currency": "INR",
    "travelers": 4,
    "travel_mode": "domestic",
    "language": "en",
}

print("=== LIVE VERIFICATION 1: Group Cost Splitting (travelers: 4, budget: ₹20,000) ===")
req = urllib.request.Request(
    f"{API_BASE}/api/plan-trip",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(req) as resp:
    init_data = json.loads(resp.read().decode("utf-8"))

job_id = init_data["job_id"]
print(f"Submitted Job ID: {job_id} | Initial Status: {init_data['status']}")

# Single blocking polling loop (~300s timeout, time.sleep(5))
timeout_sec = 300
start_time = time.time()
completed_result = None

while time.time() - start_time < timeout_sec:
    time.sleep(5)
    with urllib.request.urlopen(f"{API_BASE}/api/status/{job_id}") as poll_resp:
        status_data = json.loads(poll_resp.read().decode("utf-8"))
    
    st = status_data.get("status")
    print(f"[{time.strftime('%H:%M:%S')}] Polling status: {st}")
    
    if st == "complete":
        completed_result = status_data["result"]
        break
    elif st == "failed":
        print(f"FAILED: {status_data.get('error')}")
        sys.exit(1)

if not completed_result:
    print("ERROR: Timed out waiting for job completion")
    sys.exit(1)

print("\n=== FINAL RESULT ===")
print(json.dumps(completed_result, indent=2, ensure_ascii=False))

total = completed_result.get("total_estimated_cost", 0.0)
travelers = completed_result.get("travelers", 1)
cost_pp = completed_result.get("cost_per_person", 0.0)
expected_pp = round(total / travelers, 2)

print("\n=== RECONCILIATION VERIFICATION ===")
print(f"Total Estimated Cost: ₹{total}")
print(f"Travelers Count: {travelers}")
print(f"Cost Per Person (Actual): ₹{cost_pp}")
print(f"Cost Per Person (Expected total / {travelers}): ₹{expected_pp}")

assert travelers == 4, f"Expected travelers=4, got {travelers}"
assert cost_pp == expected_pp, f"Expected cost_per_person {expected_pp}, got {cost_pp}"
print("✅ CONFIRMED: cost_per_person strictly matches total / 4!")

# Save job_id for step 3 comparison
with open("job_id_1.txt", "w", encoding="utf-8") as f:
    f.write(job_id)
