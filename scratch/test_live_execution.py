"""
Live Execution Verification Script
Tests:
1. Real End-to-End WhatsApp Export via Headless Chromium (Playwright)
   - Intercepts window.open calls
   - Captures actual api.whatsapp.com URL and decoded payload text
2. Real Live POST /api/plan-trip for Orchestrator-Workers Pattern (Multi-City)
   - Real HTTP call against running server
   - Real polling to completion
   - Captures real job_id, elapsed time, orchestrator flag, days, and costs
3. Real Live POST /api/plan-trip for Evaluator-Optimizer Pattern (Budget Overrun)
   - Low-budget trip (₹3,000 for 3 days)
   - Real polling to completion
   - Captures real job_id, elapsed time, real cost, and real budget_exceeded_warning
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SERVER_URL = "http://127.0.0.1:8000"


def test_whatsapp_export_playwright():
    print("=" * 70)
    print("TEST 1: PLAYWRIGHT HEADLESS BROWSER WHATSAPP EXPORT E2E")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Intercept window.open calls to capture the exact URL opened
        opened_urls = []
        page.expose_function("reportOpenedUrl", lambda url: opened_urls.append(url))
        page.add_init_script("""
            const origOpen = window.open;
            window.open = function(url, target, features) {
                window.reportOpenedUrl(url);
                return null;
            };
        """)

        print(f"Navigating to {SERVER_URL} ...")
        page.goto(SERVER_URL, wait_until="networkidle")

        # Load a realistic itinerary into the application state and render it
        sample_itinerary = {
            "destination_city": "Tirupati",
            "origin_city": "Vijayawada",
            "destination_country": "India",
            "trip_length_days": 2,
            "currency": "INR",
            "travelers": 1,
            "total_estimated_cost": 14500.0,
            "recommended_stay": {
                "name": "Hotel Bliss Tirupati",
                "estimated_price_per_night": 2200.0,
                "tier": "budget"
            },
            "days": [
                {
                    "day_number": 1,
                    "city": "Tirupati",
                    "theme": "Sacred Darshan & Seshachalam Hills",
                    "morning": "Board official TTD electric bus to Tirumala for early morning Balaji Darshan.",
                    "afternoon": "Visit Silathoranam 2.5-billion-year-old Precambrian rock arch and Chakra Theertham.",
                    "evening": "Enjoy hot Tirupati Laddoo Prasadam and authentic banana-leaf Andhra dinner.",
                    "estimated_cost": 7500.0,
                    "cost_breakdown": [
                        {"item": "TTD Special Entry Darshan", "amount": 600.0},
                        {"item": "Hotel Bliss Overnight", "amount": 2200.0},
                        {"item": "Traditional Andhra Meals", "amount": 700.0},
                        {"item": "Local Green Transit", "amount": 500.0},
                        {"item": "Prasadam & Souvenirs", "amount": 3500.0}
                    ]
                },
                {
                    "day_number": 2,
                    "city": "Chandragiri",
                    "theme": "Vijayanagara Imperial Heritage",
                    "morning": "Explore Chandragiri Fort 11th-century citadel and Indo-Saracenic Raja Mahal.",
                    "afternoon": "Visit Sri Padmavathi Ammavari Temple at Tiruchanur sacred lotus shrine.",
                    "evening": "Return transit from Tirupati Central Railway Station.",
                    "estimated_cost": 7000.0,
                    "cost_breakdown": [
                        {"item": "Chandragiri Fort Entry & Guide", "amount": 500.0},
                        {"item": "Tiruchanur Temple Commute", "amount": 600.0},
                        {"item": "Lunch at Sri Lakshmi Narayana Bhavan", "amount": 900.0},
                        {"item": "Intercity Return Transit", "amount": 5000.0}
                    ]
                }
            ]
        }

        print("Injecting real itinerary into browser client runtime...")
        page.evaluate("""(itineraryData) => {
            window.currentItinerary = itineraryData;
            if (typeof renderItinerary === 'function') {
                renderItinerary(itineraryData);
            }
        }""", sample_itinerary)

        # Wait for the WhatsApp button to be visible
        btn_whatsapp = page.wait_for_selector("#btn-share-whatsapp", timeout=5000)
        assert btn_whatsapp is not None, "WhatsApp button #btn-share-whatsapp not found!"
        print("Found '#btn-share-whatsapp' button in DOM. Clicking button...")

        btn_whatsapp.click()
        page.wait_for_timeout(1000)

        assert len(opened_urls) > 0, "window.open was not triggered by WhatsApp button!"
        full_whatsapp_url = opened_urls[0]
        print("\nCaptured Real WhatsApp Target URL:")
        print(full_whatsapp_url[:120] + "...")

        parsed_url = urllib.parse.urlparse(full_whatsapp_url)
        params = urllib.parse.parse_qs(parsed_url.query)
        message_text = params.get("text", [""])[0]

        print("\nDecoded Real WhatsApp Message Payload:\n" + "-" * 50)
        print(message_text)
        print("-" * 50)

        # Assertions
        assert "api.whatsapp.com/send" in full_whatsapp_url or "wa.me" in full_whatsapp_url
        assert "Tirupati" in message_text
        assert "Hotel Bliss" in message_text
        assert "14,500" in message_text or "14500" in message_text
        assert "Day 1" in message_text
        print("\n✅ WHATSAPP E2E TEST PASSED: Real URL generated with full itinerary data!\n")

        browser.close()


def run_live_trip_job(payload: dict, test_title: str):
    print("=" * 70)
    print(f"LIVE SERVER CALL: {test_title}")
    print("=" * 70)
    print("Submitting POST /api/plan-trip with payload:")
    print(json.dumps(payload, indent=2))

    req = urllib.request.Request(
        f"{SERVER_URL}/api/plan-trip",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    t0 = time.time()
    with urllib.request.urlopen(req) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))

    job_id = res_data.get("job_id")
    print(f"\nTrip submitted! Received job_id: {job_id}")
    print("Polling /api/jobs/{job_id} until completed...")

    completed_data = None
    poll_count = 0
    while True:
        time.sleep(3)
        poll_count += 1
        elapsed = time.time() - t0
        job_url = f"{SERVER_URL}/api/status/{job_id}"
        with urllib.request.urlopen(job_url) as resp:
            status_data = json.loads(resp.read().decode("utf-8"))

        status = status_data.get("status")
        print(f"  [{elapsed:5.1f}s] Poll #{poll_count}: Status='{status}'")

        if status == "complete":
            completed_data = status_data.get("result")
            total_elapsed = elapsed
            break
        elif status == "failed":
            print(f"❌ Job failed: {status_data.get('error')}")
            return None, elapsed

    print(f"\n🎉 Job completed in {total_elapsed:.2f}s total wall-clock time!")
    return completed_data, total_elapsed


def main():
    # 1. Playwright E2E WhatsApp test
    test_whatsapp_export_playwright()

    # 2. Real Orchestrator-Workers Call (Multi-City)
    multicity_payload = {
        "origin": "Hyderabad",
        "cities": "Kurnool, Tirupati",
        "interests": "Historic forts and sacred temple heritage",
        "trip_length": 2,
        "budget": 20000.0,
        "currency": "INR"
    }
    result_orch, elapsed_orch = run_live_trip_job(multicity_payload, "ORCHESTRATOR-WORKERS (MULTI-CITY)")

    if result_orch:
        print("\n--- REAL ORCHESTRATOR RESULT ---")
        print(f"Destination: {result_orch.get('destination_city')}")
        print(f"Cities Visited: {result_orch.get('cities_visited')}")
        print(f"Orchestrator Used Flag: {result_orch.get('orchestrator_used')}")
        print(f"Trip Length Days: {result_orch.get('trip_length_days')} (Days list length: {len(result_orch.get('days', []))})")
        print(f"Total Estimated Cost: ₹{result_orch.get('total_estimated_cost'):,.2f}")
        for d in result_orch.get("days", []):
            print(f"  Day {d.get('day_number')} ({d.get('city')}): {d.get('theme')} - Cost: ₹{d.get('estimated_cost'):,.2f}")
        print(f"Intercity Transport: {result_orch.get('intercity_transport')}")

    # 3. Real Evaluator-Optimizer Call (Low-Budget Overrun)
    budget_payload = {
        "origin": "Bengaluru",
        "cities": "Goa",
        "interests": "Beach hopping, seafood shacks, and water sports",
        "trip_length": 3,
        "budget": 3000.0,
        "currency": "INR"
    }
    result_eval, elapsed_eval = run_live_trip_job(budget_payload, "EVALUATOR-OPTIMIZER (REAL BUDGET OVERRUN)")

    if result_eval:
        print("\n--- REAL EVALUATOR-OPTIMIZER RESULT ---")
        print(f"Destination: {result_eval.get('destination_city')}")
        print(f"Requested Budget: ₹3,000.00")
        print(f"Total Estimated Cost: ₹{result_eval.get('total_estimated_cost'):,.2f}")
        print(f"Budget Alert Field: {result_eval.get('budget_alert')}")
        print(f"Budget Exceeded Warning: {result_eval.get('budget_exceeded_warning')}")
        print("Daily Itemized Costs:")
        for d in result_eval.get("days", []):
            print(f"  Day {d.get('day_number')}: ₹{d.get('estimated_cost'):,.2f}")


if __name__ == "__main__":
    main()
