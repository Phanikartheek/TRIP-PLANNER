"""
Expanded Comprehensive Live Verification Script for Mobile Responsiveness & Shareable Read-Only Trip Links.
Measures DOM box metrics (scrollWidth vs clientWidth, element bounding rects, tap targets)
across 375px, 390px, 414px, and 768px viewports for Form, Itinerary, Login Modal, Q&A, and Share Page views.
"""

import json
import os
import shutil
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from trip_planner.api import db
from trip_planner.api.app import app

client = TestClient(app)
ARTIFACT_DIR = r"C:\Users\DELL\.gemini\antigravity-ide\brain\eb70b28e-00bd-4c6c-ba0d-80db5ef293b8"
VIEWPORTS = [
    {"name": "375px (iPhone SE)", "width": 375, "height": 667},
    {"name": "390px (iPhone 12/13/14)", "width": 390, "height": 844},
    {"name": "414px (iPhone Max/Plus)", "width": 414, "height": 896},
    {"name": "768px (iPad/Tablet)", "width": 768, "height": 1024},
]


def run_verification():
    print("=" * 90)
    print("  EXPANDED LIVE VERIFICATION: MOBILE RESPONSIVENESS & SHAREABLE TRIP LINKS")
    print("=" * 90)

    os.makedirs("scratch", exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    # 1. Setup completed trip in DB with full cost breakdown & QA history
    job_id = "comprehensive-responsive-uuid-888"
    db.create_job(job_id=job_id, job_type="plan", status="complete", user_email="owner@example.com")
    
    itinerary_data = {
        "destination_city": "Mysuru",
        "destination_country": "India",
        "trip_length_days": 2,
        "currency": "INR",
        "total_estimated_cost": 18000.0,
        "days": [
            {
                "day_number": 1,
                "theme": "Royal Heritage & Mysore Palace Tour",
                "morning": "Arrive in Mysuru from Bengaluru via train or car. Visit the majestic Mysore Palace (Amba Vilas) and marvel at the golden throne.",
                "afternoon": "Enjoy lunch at Hotel RRR (famous for Mysuru-style Biryani and meals). Visit Jaganmohan Palace Art Gallery.",
                "evening": "Drive up Chamundi Hill for panoramic city views at Chamundeshwari Temple.",
                "estimated_cost": 9000.0,
                "cost_breakdown": [
                    {"item": "Bengaluru-Mysuru train & auto", "amount": 2500.0},
                    {"item": "Palace & Art Gallery entry", "amount": 1000.0},
                    {"item": "Dining at RRR & dinner", "amount": 2500.0},
                    {"item": "Hotel accommodation", "amount": 3000.0}
                ]
            },
            {
                "day_number": 2,
                "theme": "Coorg Excursion & Coffee Plantation Tour",
                "morning": "Drive from Mysuru to Coorg (Madikeri). Visit Abbey Falls surrounded by lush spice estates.",
                "afternoon": "Guided coffee plantation tour and savor an authentic Kodava traditional lunch.",
                "evening": "Watch the sunset from Raja's Seat. Depart back to Bengaluru.",
                "estimated_cost": 9000.0,
                "cost_breakdown": [
                    {"item": "Private cab for Coorg roundtrip", "amount": 4000.0},
                    {"item": "Coffee estate tour & tasting", "amount": 1500.0},
                    {"item": "Kodava lunch & refreshments", "amount": 2500.0},
                    {"item": "Abbey Falls & Raja's Seat entry", "amount": 1000.0}
                ]
            }
        ],
        "packing_suggestions": [
            "Comfortable walking shoes for palace tours & waterfall trails",
            "Light jacket or sweater for cool Coorg evening weather",
            "Rain poncho / umbrella"
        ],
        "local_transport_advice": [
            "Use KSRTC Superfast or Vande Bharat train for Bengaluru-Mysuru leg.",
            "Hire a dedicated private cab for the Mysuru-Coorg segment."
        ]
    }

    db.update_job(
        job_id=job_id,
        status="complete",
        result=itinerary_data,
        qa_history=[
            {
                "question": "What is the best time to visit Mysore Palace?",
                "answer": "Morning at 10 AM when it opens or Sunday evening at 7 PM for the illumination.",
                "grounded_claims": ["Sunday evening at 7 PM for illumination"],
                "ungrounded_claims": [],
                "timestamp": 1787985000.0
            }
        ]
    )

    # 2. Test GET /api/trip/{job_id}/share
    print("\n--- STEP 1: GET /api/trip/{job_id}/share PRIVACY & STRUCTURE CHECK ---")
    res_share = client.get(f"/api/trip/{job_id}/share")
    print(f"HTTP Status Code: {res_share.status_code}")
    share_json = res_share.json()
    assert res_share.status_code == 200
    assert "user_email" not in share_json, "PRIVACY VIOLATION: user_email exposed in share endpoint!"
    assert "qa_history" not in share_json, "PRIVACY VIOLATION: qa_history exposed in share endpoint!"
    print("[OK] PRIVACY CONFIRMED: share response contains zero account or QA history metadata.")

    # 3. Test 404 Endpoint Response
    print("\n--- STEP 2: 404 INVALID LINK ENDPOINT TEST ---")
    fake_uuid = "fake-random-uuid-99999"
    res_404 = client.get(f"/api/trip/{fake_uuid}/share")
    print(f"HTTP Status Code for GET /api/trip/{fake_uuid}/share: {res_404.status_code}")
    assert res_404.status_code == 404
    print("[OK] 404 ENDPOINT CONFIRMED: Returns HTTP 404 for nonexistent job.")

    # 4. Playwright DOM Inspection Across Viewports
    print("\n--- STEP 3: PLAYWRIGHT COMPREHENSIVE VIEWPORT DOM INSPECTIONS ---")
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
    index_html_url = "file:///" + os.path.join(frontend_dir, "index.html").replace("\\", "/")
    share_html_url = "file:///" + os.path.join(frontend_dir, "share.html").replace("\\", "/") + f"?id={job_id}"
    share_404_url = "file:///" + os.path.join(frontend_dir, "share.html").replace("\\", "/") + f"?id={fake_uuid}"

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")

        for vp in VIEWPORTS:
            w, h, vp_name = vp["width"], vp["height"], vp["name"]
            print(f"\n==================== Testing Viewport: {vp_name} ({w}x{h}) ====================")

            # --- A. FORM VIEW METRICS ---
            page_form = browser.new_page(viewport={"width": w, "height": h})
            page_form.goto(index_html_url)
            page_form.wait_for_selector("#trip-form")

            form_metrics = page_form.evaluate("""() => {
                const body = document.body;
                const origin = document.querySelector('#origin').getBoundingClientRect();
                const cities = document.querySelector('#cities').getBoundingClientRect();
                const btn = document.querySelector('#submit-btn').getBoundingClientRect();
                return {
                    bodyScrollWidth: body.scrollWidth,
                    bodyClientWidth: body.clientWidth,
                    overflow: body.scrollWidth > body.clientWidth,
                    originTop: origin.top,
                    citiesTop: cities.top,
                    btnHeight: btn.height
                };
            }""")

            print(f"  [Form View] body.scrollWidth: {form_metrics['bodyScrollWidth']}px | clientWidth: {form_metrics['bodyClientWidth']}px | Horizontal Overflow: {form_metrics['overflow']}")
            print(f"  [Form View] Submit Button Height: {round(form_metrics['btnHeight'], 1)}px (min 44px target)")
            print(f"  [Form View] Vertical Field Stacking: Origin Y={round(form_metrics['originTop'], 1)}px < Cities Y={round(form_metrics['citiesTop'], 1)}px")
            
            assert not form_metrics['overflow'], f"Overflow on form view at {vp_name}!"
            assert form_metrics['btnHeight'] >= 44, f"Submit btn below 44px tap target at {vp_name}!"

            if w == 375:
                img_path = os.path.join("scratch", "mobile_375_form.png")
                page_form.screenshot(path=img_path)
                print(f"  [OK] Saved Screenshot: {img_path}")

            # --- B. LOGIN MODAL VIEW METRICS (at 375px) ---
            if w == 375:
                page_form.click("#btn-login-modal")
                page_form.wait_for_selector("#login-modal:not(.hidden)")
                modal_metrics = page_form.evaluate("""() => {
                    const modal = document.querySelector('.modal-content');
                    const input = document.querySelector('#login-email-input').getBoundingClientRect();
                    const btn = document.querySelector('#send-magic-link-btn').getBoundingClientRect();
                    return {
                        modalWidth: modal.getBoundingClientRect().width,
                        modalScrollWidth: modal.scrollWidth,
                        modalClientWidth: modal.clientWidth,
                        overflow: modal.scrollWidth > modal.clientWidth,
                        inputHeight: input.height,
                        btnHeight: btn.height
                    };
                }""")
                print(f"\n  [Login Modal] width: {round(modal_metrics['modalWidth'], 1)}px | scrollWidth: {modal_metrics['modalScrollWidth']}px | clientWidth: {modal_metrics['modalClientWidth']}px | Overflow: {modal_metrics['overflow']}")
                print(f"  [Login Modal] Input Height: {round(modal_metrics['inputHeight'], 1)}px | Send Button Height: {round(modal_metrics['btnHeight'], 1)}px")
                assert not modal_metrics['overflow'], "Overflow detected on Login Modal at 375px!"
                assert modal_metrics['inputHeight'] >= 44, "Login email input below 44px tap target!"
                assert modal_metrics['btnHeight'] >= 44, "Send Magic Link button below 44px tap target!"

                img_modal = os.path.join("scratch", "mobile_375_login_modal.png")
                page_form.screenshot(path=img_modal)
                print(f"  [OK] Saved Screenshot: {img_modal}")

            # --- C. ITINERARY & Q&A VIEW METRICS ---
            page_itin = browser.new_page(viewport={"width": w, "height": h})
            page_itin.goto(index_html_url)
            # Inject itinerary & QA data directly into page DOM state
            page_itin.evaluate("""(data) => {
                window.currentItinerary = data;
                window.currentJobId = 'comprehensive-responsive-uuid-888';
                window.renderItinerary(data);
                document.getElementById('results-section').classList.add('active');
                
                // Populate QA Section
                const qaSec = document.getElementById('qa-section');
                if (qaSec) {
                    qaSec.classList.remove('hidden');
                    const thread = document.getElementById('qa-thread');
                    if (thread) {
                        thread.innerHTML = `
                            <div class="qa-card">
                                <div class="qa-question"><strong>Q:</strong> What is the best time to visit Mysore Palace?</div>
                                <div class="qa-answer"><strong>A:</strong> Morning at 10 AM when it opens or Sunday evening at 7 PM for illumination.</div>
                                <div class="qa-grounding-badge">Grounded Claim</div>
                            </div>
                        `;
                    }
                }
            }""", itinerary_data)

            itin_metrics = page_itin.evaluate("""() => {
                const body = document.body;
                const timeline = document.querySelector('#days-timeline');
                const firstCard = document.querySelector('.day-card');
                return {
                    bodyScrollWidth: body.scrollWidth,
                    bodyClientWidth: body.clientWidth,
                    bodyOverflow: body.scrollWidth > body.clientWidth,
                    timelineScrollWidth: timeline ? timeline.scrollWidth : 0,
                    timelineClientWidth: timeline ? timeline.clientWidth : 0,
                    cardScrollWidth: firstCard ? firstCard.scrollWidth : 0,
                    cardClientWidth: firstCard ? firstCard.clientWidth : 0,
                    cardOverflow: firstCard ? firstCard.scrollWidth > firstCard.clientWidth : false
                };
            }""")

            print(f"  [Itinerary View] body scrollWidth: {itin_metrics['bodyScrollWidth']}px | clientWidth: {itin_metrics['bodyClientWidth']}px | Body Overflow: {itin_metrics['bodyOverflow']}")
            print(f"  [Itinerary View] Day Card scrollWidth: {itin_metrics['cardScrollWidth']}px | clientWidth: {itin_metrics['cardClientWidth']}px | Card Overflow: {itin_metrics['cardOverflow']}")
            assert not itin_metrics['bodyOverflow'], f"Body overflow detected on Itinerary View at {vp_name}!"
            assert not itin_metrics['cardOverflow'], f"Day Card overflow detected at {vp_name}!"

            if w == 375:
                img_itin = os.path.join("scratch", "mobile_375_itinerary.png")
                page_itin.screenshot(path=img_itin)
                print(f"  [OK] Saved Screenshot: {img_itin}")

                # Measure Q&A Section at 375px
                qa_metrics = page_itin.evaluate("""() => {
                    const qaSec = document.querySelector('#qa-section');
                    const qaInput = document.querySelector('#qa-input').getBoundingClientRect();
                    const qaBtn = document.querySelector('#qa-submit-btn').getBoundingClientRect();
                    return {
                        qaScrollWidth: qaSec.scrollWidth,
                        qaClientWidth: qaSec.clientWidth,
                        overflow: qaSec.scrollWidth > qaSec.clientWidth,
                        inputHeight: qaInput.height,
                        btnHeight: qaBtn.height
                    };
                }""")
                print(f"\n  [Q&A Section 375px] scrollWidth: {qa_metrics['qaScrollWidth']}px | clientWidth: {qa_metrics['qaClientWidth']}px | Overflow: {qa_metrics['overflow']}")
                print(f"  [Q&A Section 375px] Input Height: {round(qa_metrics['inputHeight'], 1)}px | Submit Btn Height: {round(qa_metrics['btnHeight'], 1)}px")
                assert not qa_metrics['overflow'], "Overflow detected on Q&A Section at 375px!"
                assert qa_metrics['inputHeight'] >= 44, "Q&A input below 44px tap target!"
                assert qa_metrics['btnHeight'] >= 44, "Q&A submit button below 44px tap target!"

                img_qa = os.path.join("scratch", "mobile_375_qa_section.png")
                page_itin.screenshot(path=img_qa)
                print(f"  [OK] Saved Screenshot: {img_qa}")

            # --- D. SHARE PAGE VIEW METRICS ---
            page_share = browser.new_page(viewport={"width": w, "height": h})
            page_share.route(f"**/api/trip/{job_id}/share", lambda route: route.fulfill(
                status=200, content_type="application/json", body=json.dumps(share_json)
            ))
            page_share.goto(share_html_url)
            page_share.wait_for_selector("#share-results-card")

            share_metrics = page_share.evaluate("""() => {
                const body = document.body;
                return {
                    bodyScrollWidth: body.scrollWidth,
                    bodyClientWidth: body.clientWidth,
                    overflow: body.scrollWidth > body.clientWidth
                };
            }""")
            print(f"  [Share Page] body scrollWidth: {share_metrics['bodyScrollWidth']}px | clientWidth: {share_metrics['bodyClientWidth']}px | Overflow: {share_metrics['overflow']}")
            assert not share_metrics['overflow'], f"Overflow detected on Share Page at {vp_name}!"

            if w == 375:
                img_share = os.path.join("scratch", "mobile_375_share.png")
                page_share.screenshot(path=img_share)
                print(f"  [OK] Saved Screenshot: {img_share}")

            results.append({
                "viewport": vp_name,
                "form_overflow": form_metrics['overflow'],
                "itin_overflow": itin_metrics['bodyOverflow'],
                "card_overflow": itin_metrics['cardOverflow'],
                "share_overflow": share_metrics['overflow']
            })

        # --- E. 404 SHARE ERROR PAGE AT 375px ---
        page_404 = browser.new_page(viewport={"width": 375, "height": 667})
        page_404.route(f"**/api/trip/{fake_uuid}/share", lambda route: route.fulfill(
            status=404, content_type="application/json", body=json.dumps({"detail": "Shared trip itinerary not found or processing is not complete."})
        ))
        page_404.goto(share_404_url)
        page_404.wait_for_selector("#share-error-card")
        path_404 = os.path.join("scratch", "mobile_375_share_404.png")
        page_404.screenshot(path=path_404)
        print(f"\n  [OK] 404 Error State Mobile Screenshot saved: {path_404}")

        browser.close()

    # Copy screenshots to artifacts directory
    screenshot_files = [
        "mobile_375_form.png",
        "mobile_375_login_modal.png",
        "mobile_375_itinerary.png",
        "mobile_375_qa_section.png",
        "mobile_375_share.png",
        "mobile_375_share_404.png"
    ]
    for img_name in screenshot_files:
        src = os.path.join("scratch", img_name)
        dst = os.path.join(ARTIFACT_DIR, img_name)
        if os.path.exists(src):
            shutil.copy(src, dst)
            print(f"[OK] Copied {img_name} to artifacts directory: {dst}")

    print("\n" + "=" * 90)
    print("      ALL VIEWPORT & PAGE DOM MEASUREMENTS PASSED WITH 100% SUCCESS")
    print("=" * 90)


if __name__ == "__main__":
    run_verification()
