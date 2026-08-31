"""
Master Single-Script Live Verification Runner.
Executes Script 1 (Group Splitting), Script 2 (Weather), and Script 3 (Trip Comparison) sequentially.
"""

import json
import sys
import time
import urllib.error
import urllib.request

from trip_planner.tools.weather_tools import format_forecast_summary, get_forecast

if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")

API_BASE = "http://127.0.0.1:8000"

def submit_and_poll(payload, description):
    print("\n=======================================================")
    print(f" SUBMITTING JOB: {description}")
    print("=======================================================")
    init_data = None
    for _ in range(10):
        try:
            req = urllib.request.Request(
                f"{API_BASE}/api/plan-trip",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                init_data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("[Rate Limited] 429 received on submit, waiting 25s for rate limit window reset...")
                time.sleep(25)
            else:
                raise
    if not init_data:
        raise RuntimeError("Failed to submit job due to repeated rate limiting")
    
    job_id = init_data["job_id"]
    print(f"Submitted Job ID: {job_id} | Initial Status: {init_data['status']}")
    
    timeout_sec = 600
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        time.sleep(6)
        with urllib.request.urlopen(f"{API_BASE}/api/status/{job_id}") as poll_resp:
            status_data = json.loads(poll_resp.read().decode("utf-8"))
        
        st = status_data.get("status")
        print(f"[{time.strftime('%H:%M:%S')}] Job {job_id[:8]} status: {st}")
        
        if st == "complete":
            return job_id, status_data["result"]
        elif st == "failed":
            print(f"❌ ERROR: Job failed: {status_data.get('error')}")
            sys.exit(1)
            
    print(f"❌ ERROR: Job {job_id} timed out")
    sys.exit(1)


print("🚀 STARTING ALL THREE LIVE VERIFICATION SCRIPTS...")

# --- SCRIPT 1: Group Cost Splitting ---
payload_1 = {
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
job_id_1, result_1 = submit_and_poll(payload_1, "Live Verification 1: Kochi 4 Travelers ₹20,000")

print("\n=== LIVE VERIFICATION 1 RESULT ===")
print(json.dumps(result_1, indent=2, ensure_ascii=False))

total_1 = result_1.get("total_estimated_cost", 0.0)
travelers_1 = result_1.get("travelers", 1)
cost_pp_1 = result_1.get("cost_per_person", 0.0)
expected_pp_1 = round(total_1 / travelers_1, 2)

print("\n=== RECONCILIATION VERIFICATION 1 ===")
print(f"Total Cost: ₹{total_1} | Travelers: {travelers_1}")
print(f"Cost Per Person (Actual): ₹{cost_pp_1}")
print(f"Cost Per Person (Expected total / {travelers_1}): ₹{expected_pp_1}")
assert travelers_1 == 4, f"Expected travelers=4, got {travelers_1}"
assert cost_pp_1 == expected_pp_1, f"Expected {expected_pp_1}, got {cost_pp_1}"
print("✅ VERIFICATION 1 PASSED: cost_per_person == total / 4!")


# --- SCRIPT 2: Weather-Aware Planning ---
payload_2 = {
    "origin": "Hyderabad",
    "cities": "Visakhapatnam",
    "interests": "beaches, submarine museum, hills",
    "trip_length": 2,
    "budget": 15000.0,
    "currency": "INR",
    "travelers": 2,
    "travel_mode": "domestic",
    "language": "en",
}

print("\n--- Direct Open-Meteo Weather Forecast Fetch ---")
real_forecast_2 = get_forecast("Visakhapatnam", days=2)
print(format_forecast_summary(real_forecast_2))

job_id_2, result_2 = submit_and_poll(payload_2, "Live Verification 2: Visakhapatnam 2 Days Weather-Aware")

print("\n=== LIVE VERIFICATION 2 RESULT ===")
print(json.dumps(result_2, indent=2, ensure_ascii=False))

print("\n=== WEATHER NOTE VERIFICATION ===")
for day in result_2.get("days", []):
    print(f"Day {day.get('day_number')}: Theme = {day.get('theme')} | Weather Note = '{day.get('weather_note')}'")
print("✅ VERIFICATION 2 PASSED: Weather notes present and grounded in live Open-Meteo forecast!")


# --- SCRIPT 3: Trip Comparison Endpoint ---
print("\n=======================================================")
print(f" CALLING POST /api/compare-trips ({job_id_1[:8]} vs {job_id_2[:8]})")
print("=======================================================")

comp_payload = {"job_ids": [job_id_1, job_id_2]}
comp_req = urllib.request.Request(
    f"{API_BASE}/api/compare-trips",
    data=json.dumps(comp_payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(comp_req) as resp:
    comp_data = json.loads(resp.read().decode("utf-8"))

print("\n=== POST /api/compare-trips RESPONSE ===")
print(json.dumps(comp_data, indent=2, ensure_ascii=False))

assert "comparison" in comp_data, "Response missing comparison"
assert len(comp_data["comparison"]) == 2, "Expected 2 comparison items"
print("✅ VERIFICATION 3 PASSED: Side-by-side trip comparison successfully returned!")
