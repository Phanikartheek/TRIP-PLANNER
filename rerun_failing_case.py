"""
Script to re-run the exact failing case:
Bengaluru -> Goa, budget 3000, 3 days
Polls to completion and logs:
- Job ID
- Status (failed vs complete)
- Error message (if failed)
- Total cost and budget warnings (if complete)
- Elapsed time
"""

import json
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SERVER_URL = "http://127.0.0.1:8000"

payload = {
    "origin": "Bengaluru",
    "cities": "Goa",
    "interests": "Beach hopping, seafood shacks, and water sports",
    "trip_length": 3,
    "budget": 3000.0,
    "currency": "INR"
}

print("=" * 70)
print("RE-RUNNING EXACT FAILING CASE: BENGALURU -> GOA (BUDGET ₹3,000, 3 DAYS)")
print("=" * 70)

req = urllib.request.Request(
    f"{SERVER_URL}/api/plan-trip",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

t0 = time.time()
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode("utf-8"))

job_id = res.get("job_id")
print(f"Submitted! Real Job ID: {job_id}")
print("Polling /api/status/{job_id} ...")

poll = 0
while True:
    time.sleep(3)
    poll += 1
    elapsed = time.time() - t0
    job_url = f"{SERVER_URL}/api/status/{job_id}"
    with urllib.request.urlopen(job_url) as resp:
        status_data = json.loads(resp.read().decode("utf-8"))

    status = status_data.get("status")
    print(f"  [{elapsed:5.1f}s] Poll #{poll}: status='{status}'")

    if status in ("complete", "failed"):
        print("\n" + "=" * 70)
        print(f"JOB TERMINATED WITH STATUS: {status.upper()}")
        print("=" * 70)
        print(f"Real Job ID: {job_id}")
        print(f"Total Wall-Clock Elapsed Time: {elapsed:.2f}s")
        print(f"Error Field: {status_data.get('error')}")

        result = status_data.get("result")
        if result:
            print(f"Total Estimated Cost: ₹{result.get('total_estimated_cost', 0):,.2f}")
            print(f"Days Count: {len(result.get('days', []))}")
            print(f"Budget Exceeded Warning: {result.get('budget_exceeded_warning')}")
            print(f"Budget Alert: {result.get('budget_alert')}")
        else:
            print("Result: None (Correctly withheld on failure)")
        break
