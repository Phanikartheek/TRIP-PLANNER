"""
Controlled Production Concurrency and Scalability Load Test Harness.
Simulates 5, 10, and 20 concurrent users submitting trip requests and polling to completion.
Mocks the AI execution to preserve provider quota while measuring real FastAPI ASGI routing,
SQLite WAL locking under concurrency, job lifecycle transitions, memory, and P95 latency.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

# Ensure backend package is in python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx
from trip_planner.api.app import app, job_repo
from trip_planner.api.db import init_db
from trip_planner.schemas.models import TripItinerary


def _generate_mock_itinerary(cities: str = "Goa", trip_length: int = 3) -> dict[str, Any]:
    """Generates a valid, mathematically sound mock itinerary."""
    days = []
    for d in range(1, trip_length + 1):
        days.append({
            "day_number": d,
            "theme": f"Day {d} in {cities} - Scenic Exploration",
            "morning": f"Morning walk along the coast and cultural landmarks in {cities}.",
            "afternoon": f"Afternoon visit to heritage sites and regional cuisine lunch in {cities}.",
            "evening": f"Sunset viewing and local market handicrafts in {cities}.",
            "night": f"Dinner and relaxed evening in {cities}.",
            "estimated_cost": 2500.0,
            "cost_breakdown": [
                {"item": "Sightseeing", "amount": 1000.0},
                {"item": "Food & Dining", "amount": 1500.0},
            ],
        })
    itin = TripItinerary(
        destination_city=cities,
        destination_country="India",
        trip_length_days=trip_length,
        travelers=1,
        total_estimated_cost=2500.0 * trip_length,
        cost_per_person=2500.0 * trip_length,
        days=days,
        packing_suggestions=["Comfortable clothing", "Walking shoes", "Phone charger"],
    )
    return itin.model_dump()


def _simulated_run_crew_sync(inputs: dict[str, Any]) -> dict[str, Any]:
    """Simulates realistic agent runtime (0.15s) without calling external LLMs."""
    time.sleep(0.15)
    cities = inputs.get("cities", "Goa")
    trip_len = int(inputs.get("trip_length", 3))
    return _generate_mock_itinerary(cities=cities, trip_length=trip_len)


async def simulate_user(
    client: httpx.AsyncClient,
    user_idx: int,
    results: list[dict[str, Any]],
    lock: asyncio.Lock,
) -> None:
    """Simulates an individual user submitting a trip and polling until complete."""
    cities = f"Destination_{user_idx % 5}"
    payload = {
        "origin": "Mumbai",
        "cities": cities,
        "interests": f"Culture, food, sightseeing for user {user_idx}",
        "trip_length": 3,
        "budget": 25000.0,
        "currency": "INR",
        "travelers": 1,
        "language": "en",
    }
    client_ip = f"192.168.1.{100 + user_idx}"
    headers = {
        "X-Forwarded-For": client_ip,
        "Content-Type": "application/json",
    }

    t0 = time.time()
    try:
        # 1. Submit trip planning request
        submit_res = await client.post("/api/plan-trip", json=payload, headers=headers)
        sub_latency = time.time() - t0

        if submit_res.status_code != 200:
            async with lock:
                results.append({
                    "user_idx": user_idx,
                    "status_code": submit_res.status_code,
                    "error": submit_res.text,
                    "submit_latency": sub_latency,
                    "total_latency": time.time() - t0,
                    "success": False,
                })
            return

        job_data = submit_res.json()
        job_id = job_data["job_id"]

        # 2. Poll for status
        poll_start = time.time()
        completed = False
        poll_count = 0
        final_status = "pending"

        while time.time() - poll_start < 10.0:
            poll_count += 1
            await asyncio.sleep(0.05)  # Fast poll in test harness
            status_res = await client.get(f"/api/status/{job_id}", headers=headers)
            if status_res.status_code == 200:
                s_data = status_res.json()
                final_status = s_data.get("status", "pending")
                if final_status == "complete":
                    completed = True
                    break
                elif final_status == "failed":
                    break

        total_latency = time.time() - t0
        async with lock:
            results.append({
                "user_idx": user_idx,
                "status_code": submit_res.status_code,
                "final_status": final_status,
                "submit_latency": round(sub_latency, 4),
                "total_latency": round(total_latency, 4),
                "poll_count": poll_count,
                "success": completed,
            })
    except Exception as exc:
        async with lock:
            results.append({
                "user_idx": user_idx,
                "status_code": 0,
                "error": str(exc),
                "submit_latency": 0.0,
                "total_latency": round(time.time() - t0, 4),
                "success": False,
            })


def _mock_get_forecast(city: str, days: int = 5) -> list[dict[str, Any]]:
    return [
        {"date": f"2026-09-0{d}", "condition": "Clear sky", "temp_high": 28.0, "temp_low": 20.0, "rain_probability": 10}
        for d in range(1, days + 1)
    ]


async def run_scenario(concurrency: int) -> dict[str, Any]:
    """Executes a load-test scenario for a specific number of concurrent users."""
    print("\n==================================================")
    print(f"RUNNING SCENARIO: {concurrency} CONCURRENT USERS")
    print("==================================================")

    # Initialize clean SQLite DB in a temporary directory
    test_db = Path(__file__).resolve().parent / f"test_load_{concurrency}.db"
    if test_db.exists():
        try:
            test_db.unlink()
        except Exception:
            pass

    init_db(db_path=test_db)
    job_repo.db_path = test_db

    # Ensure proxy trusting is enabled for test
    os.environ["TRUST_PROXY"] = "true"

    transport = httpx.ASGITransport(app=app)
    results: list[dict[str, Any]] = []
    lock = asyncio.Lock()

    t_start = time.time()
    with patch("trip_planner.api.app._run_crew_sync", side_effect=_simulated_run_crew_sync), \
         patch("trip_planner.api.app.get_forecast", side_effect=_mock_get_forecast):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            tasks = [
                simulate_user(client, i, results, lock)
                for i in range(concurrency)
            ]
            await asyncio.gather(*tasks)

    total_duration = time.time() - t_start

    # Compute statistics
    successes = [r for r in results if r.get("success")]
    failures = [r for r in results if not r.get("success")]
    sub_latencies = sorted([r["submit_latency"] for r in results if "submit_latency" in r])
    tot_latencies = sorted([r["total_latency"] for r in results if "total_latency" in r])

    def calc_percentile(arr: list[float], pct: float) -> float:
        if not arr:
            return 0.0
        k = int(len(arr) * pct)
        return round(arr[min(k, len(arr) - 1)], 4)

    summary = {
        "concurrency": concurrency,
        "total_requests": len(results),
        "success_count": len(successes),
        "failure_count": len(failures),
        "success_rate_pct": round((len(successes) / len(results)) * 100.0, 1),
        "total_wall_time_sec": round(total_duration, 2),
        "throughput_req_per_sec": round(len(results) / total_duration, 2) if total_duration > 0 else 0.0,
        "submit_latency": {
            "avg": round(sum(sub_latencies) / len(sub_latencies), 4) if sub_latencies else 0.0,
            "p50": calc_percentile(sub_latencies, 0.50),
            "p95": calc_percentile(sub_latencies, 0.95),
            "max": sub_latencies[-1] if sub_latencies else 0.0,
        },
        "total_job_latency": {
            "avg": round(sum(tot_latencies) / len(tot_latencies), 4) if tot_latencies else 0.0,
            "p50": calc_percentile(tot_latencies, 0.50),
            "p95": calc_percentile(tot_latencies, 0.95),
            "max": tot_latencies[-1] if tot_latencies else 0.0,
        },
    }

    print(f"Results for {concurrency} users:")
    print(f"  Success Rate: {summary['success_rate_pct']}% ({summary['success_count']}/{summary['total_requests']})")
    print(f"  Submit Latency Avg / P95: {summary['submit_latency']['avg']}s / {summary['submit_latency']['p95']}s")
    print(f"  Job Latency Avg / P95: {summary['total_job_latency']['avg']}s / {summary['total_job_latency']['p95']}s")
    print(f"  Total Duration: {summary['total_wall_time_sec']}s")

    # Cleanup test DB
    try:
        test_db.unlink(missing_ok=True)
        wal = test_db.with_name(f"{test_db.name}-wal")
        shm = test_db.with_name(f"{test_db.name}-shm")
        wal.unlink(missing_ok=True)
        shm.unlink(missing_ok=True)
    except Exception:
        pass

    return summary


async def main():
    scenario_5 = await run_scenario(5)
    scenario_10 = await run_scenario(10)
    scenario_20 = await run_scenario(20)

    print("\n==================================================")
    print("LOAD TEST MATRIX SUMMARY")
    print("==================================================")
    for s in (scenario_5, scenario_10, scenario_20):
        print(f"Users: {s['concurrency']:2d} | Success: {s['success_rate_pct']}% | Submit P95: {s['submit_latency']['p95']}s | Job P95: {s['total_job_latency']['p95']}s")


if __name__ == "__main__":
    asyncio.run(main())
