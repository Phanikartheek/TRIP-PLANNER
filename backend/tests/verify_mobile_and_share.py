"""
Live End-to-End Verification for Mobile Responsiveness & Shareable Read-Only Trip Links.
Includes real Groq API execution, DOM box-overflow evaluation, Playwright screenshots, and 404 handling.
"""

import json
import os
import shutil
import sys
import threading
import time

import requests
import uvicorn
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from trip_planner.api.app import app

# Ensure UTF-8 stdout printing on Windows cp1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

PORT = 8009
BASE_URL = f"http://127.0.0.1:{PORT}"
SCRATCH_DIR = r"c:\Users\DELL\Downloads\trip_planner (1)\trip_planner\scratch"
ARTIFACT_DIR = r"C:\Users\DELL\.gemini\antigravity-ide\brain\eb70b28e-00bd-4c6c-ba0d-80db5ef293b8"


def start_server():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def run_verification():
    print("=" * 80)
    print("    LIVE VERIFICATION: MOBILE RESPONSIVENESS & SHAREABLE TRIP LINKS")
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
                print(f"[OK] Backend server responsive: {r.json()['service']}")
                break
        except Exception:
            time.sleep(0.5)

    os.makedirs(SCRATCH_DIR, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    # ----------------------------------------------------
    # STEP 1: REAL POST /api/plan-trip HTTP Request
    # ----------------------------------------------------
    print("\n--- STEP 1: REAL POST /api/plan-trip HTTP REQUEST ---")
    session = requests.Session()
    plan_payload = {
        "origin": "Bengaluru",
        "cities": "Mysuru, Coorg",
        "interests": "palaces, coffee plantations, waterfalls",
        "trip_length": 2,
        "budget": 18000,
        "currency": "INR",
        "travel_mode": "domestic",
        "language": "en"
    }

    start_time = time.time()
    res_plan = session.post(f"{BASE_URL}/api/plan-trip", json=plan_payload)
    print(f"HTTP Status Code: {res_plan.status_code}")
    plan_json = res_plan.json()
    job_id = plan_json.get("job_id")
    print(f"Captured Real UUID4 Job ID: {job_id}")

    # Poll status until complete
    print(f"Polling GET /api/status/{job_id} until completion...")
    status = "pending"
    poll_count = 0
    while status in ("pending", "running"):
        time.sleep(3)
        poll_count += 1
        st_res = session.get(f"{BASE_URL}/api/status/{job_id}")
        st_json = st_res.json()
        status = st_json.get("status")
        elapsed = round(time.time() - start_time, 1)
        print(f"  [Poll #{poll_count} | Elapsed: {elapsed}s] Status: {status}")
        if status == "complete":
            break
        elif status == "failed":
            raise RuntimeError(f"Job execution failed: {st_json.get('error')}")

    total_elapsed = round(time.time() - start_time, 1)
    print(f"[OK] Real Trip Job Completed in {total_elapsed} seconds!")

    # ----------------------------------------------------
    # STEP 2: GET /api/trip/{job_id}/share Raw Response
    # ----------------------------------------------------
    print(f"\n--- STEP 2: GET /api/trip/{job_id}/share PRIVACY & STRUCTURE CHECK ---")
    res_share = session.get(f"{BASE_URL}/api/trip/{job_id}/share")
    print(f"HTTP Status Code: {res_share.status_code}")
    share_json = res_share.json()
    print(f"Raw Share API Response:\n{json.dumps(share_json, indent=2)}")

    assert res_share.status_code == 200
    assert "user_email" not in share_json, "PRIVACY FAILURE: user_email exposed in share response!"
    assert "qa_history" not in share_json, "PRIVACY FAILURE: qa_history exposed in share response!"
    print("[OK] PRIVACY CONFIRMED: share response contains zero account or QA history metadata.")

    # ----------------------------------------------------
    # STEP 3: PLAYWRIGHT MOBILE VIEWPORT & LAYOUT METRICS
    # ----------------------------------------------------
    print("\n--- STEP 3: PLAYWRIGHT MOBILE VIEWPORT & DOM OVERFLOW INSPECTION ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")

        # 3a. Mobile 375x667 Viewport Inspection (iPhone SE)
        page_mobile = browser.new_page(viewport={"width": 375, "height": 667})
        page_mobile.goto(f"{BASE_URL}/")
        page_mobile.wait_for_selector("#trip-form")

        # Evaluate body & main form box dimensions for horizontal overflow
        overflow_metrics = page_mobile.evaluate("""() => {
            const body = document.body;
            const container = document.querySelector('.app-container');
            const form = document.querySelector('#trip-form');
            return {
                bodyScrollWidth: body.scrollWidth,
                bodyClientWidth: body.clientWidth,
                containerScrollWidth: container.scrollWidth,
                containerClientWidth: container.clientWidth,
                hasBodyHorizontalScroll: body.scrollWidth > body.clientWidth,
                submitBtnBounds: document.querySelector('#submit-btn').getBoundingClientRect()
            };
        }""")

        print("Mobile 375px Layout DOM Metrics:")
        print(f"  Body scrollWidth vs clientWidth: {overflow_metrics['bodyScrollWidth']}px / {overflow_metrics['bodyClientWidth']}px")
        print(f"  Container scrollWidth vs clientWidth: {overflow_metrics['containerScrollWidth']}px / {overflow_metrics['containerClientWidth']}px")
        print(f"  Submit Button Height (min 44px required): {round(overflow_metrics['submitBtnBounds']['height'], 1)}px")
        assert not overflow_metrics['hasBodyHorizontalScroll'], "LAYOUT FAILURE: Horizontal scroll detected on 375px mobile viewport!"
        print("[OK] DOM INSPECTION CONFIRMED: Zero horizontal overflow on 375px mobile form.")

        # Take screenshot 1: Main Form Mobile 375x667
        path_form_375 = os.path.join(SCRATCH_DIR, "mobile_375_form.png")
        page_mobile.screenshot(path=path_form_375)
        print(f"[OK] Mobile 375px Form Screenshot saved: {path_form_375}")

        # 3b. Mobile 375x667 Share Page Inspection
        page_share_375 = browser.new_page(viewport={"width": 375, "height": 667})
        page_share_375.goto(f"{BASE_URL}/share.html?id={job_id}")
        page_share_375.wait_for_selector("#share-results-card")

        share_overflow_metrics = page_share_375.evaluate("""() => {
            const body = document.body;
            const timeline = document.querySelector('#share-days-timeline');
            return {
                bodyScrollWidth: body.scrollWidth,
                bodyClientWidth: body.clientWidth,
                timelineScrollWidth: timeline.scrollWidth,
                timelineClientWidth: timeline.clientWidth,
                hasBodyHorizontalScroll: body.scrollWidth > body.clientWidth
            };
        }""")
        print("\nMobile 375px Share Page Layout Metrics:")
        print(f"  Body scrollWidth vs clientWidth: {share_overflow_metrics['bodyScrollWidth']}px / {share_overflow_metrics['bodyClientWidth']}px")
        assert not share_overflow_metrics['hasBodyHorizontalScroll'], "LAYOUT FAILURE: Horizontal scroll detected on 375px share page!"
        print("[OK] DOM INSPECTION CONFIRMED: Zero horizontal overflow on 375px shared itinerary page.")

        # Take screenshot 2: Mobile 375x667 Share Page
        path_share_375 = os.path.join(SCRATCH_DIR, "mobile_375_share.png")
        page_share_375.screenshot(path=path_share_375)
        print(f"[OK] Mobile 375px Share Page Screenshot saved: {path_share_375}")

        # 3c. Desktop 1280x800 Share Page Inspection
        page_share_desktop = browser.new_page(viewport={"width": 1280, "height": 800})
        page_share_desktop.goto(f"{BASE_URL}/share.html?id={job_id}")
        page_share_desktop.wait_for_selector("#share-results-card")
        path_share_desktop = os.path.join(SCRATCH_DIR, "desktop_share.png")
        page_share_desktop.screenshot(path=path_share_desktop)
        print(f"[OK] Desktop Share Page Screenshot saved: {path_share_desktop}")

        # 3d. 404 Invalid Link Share Page Inspection
        fake_uuid = "fake-random-uuid-99999"
        print(f"\n--- STEP 4: 404 INVALID LINK TEST (job_id = {fake_uuid}) ---")
        res_404 = session.get(f"{BASE_URL}/api/trip/{fake_uuid}/share")
        print(f"HTTP Status Code for GET /api/trip/{fake_uuid}/share: {res_404.status_code}")
        print(f"Raw 404 Response Body: {res_404.json()}")
        assert res_404.status_code == 404

        page_404 = browser.new_page(viewport={"width": 375, "height": 667})
        page_404.goto(f"{BASE_URL}/share.html?id={fake_uuid}")
        page_404.wait_for_selector("#share-error-card")
        path_404 = os.path.join(SCRATCH_DIR, "mobile_375_share_404.png")
        page_404.screenshot(path=path_404)
        print(f"[OK] 404 Error State Mobile Screenshot saved: {path_404}")

        browser.close()

    # Copy screenshots to artifacts directory for visual inspection and embedding
    for img_name in ["mobile_375_form.png", "mobile_375_share.png", "desktop_share.png", "mobile_375_share_404.png"]:
        src = os.path.join(SCRATCH_DIR, img_name)
        dst = os.path.join(ARTIFACT_DIR, img_name)
        if os.path.exists(src):
            shutil.copy(src, dst)
            print(f"[OK] Copied {img_name} to artifacts directory: {dst}")

    print("\n" + "=" * 80)
    print("      ALL LIVE VERIFICATIONS COMPLETED SUCCESSFULLY WITH 100% PASS")
    print("=" * 80)


if __name__ == "__main__":
    run_verification()
