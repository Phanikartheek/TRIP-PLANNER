"""
Single-Script Live Verification 2 — Weather-Aware Planning & Open-Meteo Integration
Submits request for Visakhapatnam, polls to completion, fetches real Open-Meteo forecast,
and compares agent's weather_note with live forecast data.
"""

import json
import sys
import time
import urllib.request

from trip_planner.tools.weather_tools import format_forecast_summary, get_forecast

sys.stdout.reconfigure(encoding="utf-8")

API_BASE = "http://127.0.0.1:8000"

payload = {
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

print("=== LIVE VERIFICATION 2: Weather-Aware Planning (Visakhapatnam, 2 Days) ===")

# 1. Fetch real Open-Meteo forecast directly
real_forecast = get_forecast("Visakhapatnam", days=2)
real_summary = format_forecast_summary(real_forecast)
print("\n--- Direct Open-Meteo Forecast Output ---")
print(real_summary)

# 2. Submit trip planning job
req = urllib.request.Request(
    f"{API_BASE}/api/plan-trip",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(req) as resp:
    init_data = json.loads(resp.read().decode("utf-8"))

job_id = init_data["job_id"]
print(f"\nSubmitted Job ID: {job_id} | Initial Status: {init_data['status']}")

# Single blocking polling loop (~300s timeout)
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

print("\n=== WEATHER NOTE VERIFICATION ===")
for day in completed_result.get("days", []):
    print(f"Day {day.get('day_number')}: Theme = {day.get('theme')} | Weather Note = '{day.get('weather_note')}'")

# Save job_id_2 for comparison verification
with open("job_id_2.txt", "w", encoding="utf-8") as f:
    f.write(job_id)
