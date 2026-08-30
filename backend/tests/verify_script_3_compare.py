"""
Single-Script Live Verification 3 — Trip Comparison Endpoint
Calls POST /api/compare-trips with job_id_1 and job_id_2 and prints the structural comparison.
"""

import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

API_BASE = "http://127.0.0.1:8000"

with open("job_id_1.txt", encoding="utf-8") as f:
    job_id_1 = f.read().strip()

with open("job_id_2.txt", encoding="utf-8") as f:
    job_id_2 = f.read().strip()

print(f"=== LIVE VERIFICATION 3: Trip Comparison ({job_id_1} vs {job_id_2}) ===")

req_payload = {"job_ids": [job_id_1, job_id_2]}

req = urllib.request.Request(
    f"{API_BASE}/api/compare-trips",
    data=json.dumps(req_payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(req) as resp:
    comp_data = json.loads(resp.read().decode("utf-8"))

print("\n=== POST /api/compare-trips RESPONSE ===")
print(json.dumps(comp_data, indent=2, ensure_ascii=False))

assert "comparison" in comp_data, "Response missing comparison field"
assert len(comp_data["comparison"]) == 2, "Expected 2 trip items in comparison"
print("✅ CONFIRMED: POST /api/compare-trips returned valid side-by-side comparison!")
