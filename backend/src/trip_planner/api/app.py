"""
FastAPI application exposing the Trip Planner agent pipeline via REST API
and serving the frontend web dashboard.
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any

import resend
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from trip_planner.api import db
from trip_planner.schemas.models import (
    DestinationQuestion,
    QAResponse,
    RevisionRequest,
    SmartRequest,
    SmartRequestResponse,
    TripPlanRequest,
    clean_float,
)
from trip_planner.tools import format_forecast_summary, get_forecast

load_dotenv()
logger = logging.getLogger("trip_planner.api")

# Initialize Rate Limiter keyed by remote IP
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Initializes the SQLite job store, reconciles interrupted jobs, and starts reminder task."""
    db.init_db()
    task = asyncio.create_task(_reminder_background_worker())
    yield
    task.cancel()


app = FastAPI(
    title="AI Trip Planner API",
    description="Multi-agent trip planning engine with CrewAI and Groq",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    from fastapi.responses import JSONResponse

    detail = str(getattr(exc, "detail", "Rate limit exceeded"))
    response = JSONResponse(
        {"error": f"Rate limit exceeded: {detail}"},
        status_code=429,
    )
    response.headers["Retry-After"] = "3600"
    return response


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def check_and_send_reminders(db_path: Path | str | None = None) -> list[str]:
    """
    Checks DB for completed jobs starting tomorrow (travel_date == tomorrow) with reminder_sent=False
    and valid user_email. Dispatches reminder email and marks reminder_sent=True.
    """
    from datetime import datetime, timedelta
    tomorrow_str = (datetime.now().date() + timedelta(days=1)).isoformat()
    processed_job_ids: list[str] = []

    with db.get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT job_id, user_email, result, travel_date
            FROM jobs
            WHERE status = 'complete'
              AND (reminder_sent = 0 OR reminder_sent IS NULL)
              AND travel_date = ?
              AND user_email IS NOT NULL
              AND user_email != '';
            """,
            (tomorrow_str,),
        )
        rows = cursor.fetchall()
        for row in rows:
            jid = row["job_id"]
            email = row["user_email"]
            res_dict = json.loads(row["result"]) if row["result"] else {}
            city = res_dict.get("destination_city", "your destination")
            length = res_dict.get("trip_length_days", 1)

            email_html = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 500px; border: 1px solid #e0e0e0; border-radius: 8px;">
              <h2 style="color: #4f46e5;">✈️ Trip Reminder: {city} Tomorrow!</h2>
              <p>Your {length}-day trip to <strong>{city}</strong> starts tomorrow ({tomorrow_str}).</p>
              <p>Don't forget to review your packing checklist and itinerary details!</p>
            </div>
            """
            email_sent = False
            if os.getenv("RESEND_API_KEY"):
                try:
                    resend.Emails.send({
                        "from": "AI Trip Planner <onboarding@resend.dev>",
                        "to": [email],
                        "subject": f"Reminder: Your trip to {city} is tomorrow!",
                        "html": email_html,
                    })
                    email_sent = True
                except Exception as e:
                    logger.error(f"Failed to send reminder email to {email}: {e}")

            if not email_sent:
                logger.info(f"[REMINDER LOG] Sent trip reminder to {email} for job {jid} (City: {city}, Date: {tomorrow_str})")
                print(f"[REMINDER LOG] Sent trip reminder to {email} for job {jid} (City: {city}, Date: {tomorrow_str})", flush=True)

            db.update_job(jid, reminder_sent=True, db_path=db_path)
            processed_job_ids.append(jid)

    return processed_job_ids


async def _reminder_background_worker():
    while True:
        try:
            check_and_send_reminders()
        except Exception as e:
            logger.error(f"Error in reminder background worker loop: {e}")
        await asyncio.sleep(3600)


# Locate frontend directory relative to project root
API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parents[3]  # app.py -> api -> trip_planner -> src -> backend -> root
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = Path.cwd() / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/style.css")
async def serve_style():
    style_file = FRONTEND_DIR / "style.css"
    if style_file.exists():
        return FileResponse(str(style_file), media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")


@app.get("/app.js")
async def serve_app_js():
    js_file = FRONTEND_DIR / "app.js"
    if js_file.exists():
        return FileResponse(str(js_file), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")


@app.get("/manifest.json")
async def serve_manifest():
    manifest_file = FRONTEND_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(str(manifest_file), media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="manifest.json not found")


@app.get("/sw.js")
async def serve_sw():
    sw_file = FRONTEND_DIR / "sw.js"
    if sw_file.exists():
        return FileResponse(str(sw_file), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="sw.js not found")




class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address for magic link login")


class VerifyTokenRequest(BaseModel):
    token: str = Field(..., description="Magic token or full verification URL")


class ChecklistItemPatch(BaseModel):
    item: str = Field(..., description="Checklist item text")
    checked: bool = Field(..., description="Checked boolean state")


class JobStatusResponse(BaseModel):
    job_id: str
    status: str = Field(description="Job status: pending, running, complete, or failed")
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float | None = None
    travel_date: str | None = None
    reminder_sent: bool | None = None
    checklist: list[dict[str, Any]] | None = None


# Comprehensive registry of Indian travel hub coordinates (Latitude, Longitude)
CITY_GEO_COORDS: dict[str, tuple[float, float]] = {
    "vijayawada": (16.5062, 80.6480),
    "bezawada": (16.5062, 80.6480),
    "guntur": (16.3067, 80.4365),
    "amaravati": (16.5417, 80.5158),
    "ongole": (15.5057, 80.0499),
    "nellore": (14.4426, 79.9865),
    "nellor": (14.4426, 79.9865),
    "tirupati": (13.6288, 79.4192),
    "tirumala": (13.6288, 79.4192),
    "hyderabad": (17.3850, 78.4867),
    "visakhapatnam": (17.6868, 83.2185),
    "vizag": (17.6868, 83.2185),
    "rajahmundry": (17.0005, 81.8040),
    "kakinada": (16.9891, 82.2475),
    "kurnool": (15.8281, 78.0373),
    "anantapur": (14.6819, 77.6006),
    "kadapa": (14.4673, 78.8242),
    "chennai": (13.0827, 80.2707),
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "mysuru": (12.2958, 76.6394),
    "mysore": (12.2958, 76.6394),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "delhi ncr": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777),
    "pune": (18.5204, 73.8567),
    "goa": (15.2993, 74.1240),
    "north goa": (15.5527, 73.7517),
    "south goa": (15.2832, 73.9862),
    "old goa": (15.5009, 73.9116),
    "manali": (32.2396, 77.1887),
    "shimla": (31.1048, 77.1734),
    "dharamshala": (32.2190, 76.3234),
    "jaipur": (26.9124, 75.7873),
    "udaipur": (24.5854, 73.7125),
    "jodhpur": (26.2389, 73.0243),
    "agra": (27.1767, 78.0081),
    "varanasi": (25.3176, 82.9739),
    "kashi": (25.3176, 82.9739),
    "kolkata": (22.5726, 88.3639),
    "kochi": (9.9312, 76.2673),
    "cochin": (9.9312, 76.2673),
    "munnar": (10.0889, 77.0595),
    "alleppey": (9.4981, 76.3388),
    "alappuzha": (9.4981, 76.3388),
    "rishikesh": (30.0869, 78.2676),
    "haridwar": (29.9457, 78.1642),
    "dehradun": (30.3165, 78.0322),
}


def get_city_coordinates(city_name: str) -> tuple[float, float] | None:
    """Finds lat/lon for a city name using canonical mapping and fuzzy matching."""
    if not city_name:
        return None
    name_clean = city_name.strip().lower()
    if name_clean in CITY_GEO_COORDS:
        return CITY_GEO_COORDS[name_clean]
    for k, coords in CITY_GEO_COORDS.items():
        if k in name_clean or name_clean in k:
            return coords
    return None


def calculate_distance_km(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """Calculates Haversine distance in kilometers between two lat/lon points."""
    import math

    lat1, lon1 = coord1
    lat2, lon2 = coord2
    r = 6371.0  # Earth radius in km

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 1)


def optimize_city_route(origin_name: str, candidate_cities: list[str]) -> list[str]:
    """
    Sequences candidate cities using a Nearest-Neighbor corridor starting from origin.
    Prevents zig-zag backtracking (e.g., ensures Vijayawada -> Guntur -> Nellore -> Tirupati,
    not Vijayawada -> Nellore -> Guntur -> Tirupati).
    """
    if len(candidate_cities) <= 1:
        return list(candidate_cities)

    # Normalize candidate list, preserving canonical casing
    unique_candidates: list[str] = []
    seen = set()
    for c in candidate_cities:
        c_clean = c.strip()
        if c_clean.lower() not in seen and c_clean.lower() != origin_name.strip().lower():
            seen.add(c_clean.lower())
            unique_candidates.append(c_clean)

    if len(unique_candidates) <= 1:
        return unique_candidates

    current_hub = origin_name.strip()
    current_coords = get_city_coordinates(current_hub)

    remaining = list(unique_candidates)
    optimized_sequence: list[str] = []

    while remaining:
        if not current_coords:
            optimized_sequence.extend(remaining)
            break

        best_city = remaining[0]
        min_dist = float("inf")

        for cand in remaining:
            cand_coords = get_city_coordinates(cand)
            if cand_coords:
                dist = calculate_distance_km(current_coords, cand_coords)
            else:
                dist = 500.0
            if dist < min_dist:
                min_dist = dist
                best_city = cand

        optimized_sequence.append(best_city)
        remaining.remove(best_city)
        current_hub = best_city
        current_coords = get_city_coordinates(best_city)

    return optimized_sequence


def reconcile_multi_city_itinerary(
    out_dict: dict[str, Any],
    raw_cities: list[str] | None = None,
    origin_name: str = "Origin",
    budget_val: float = 25000.0,
) -> None:

    """
    Robustly reconciles multi-city itineraries by inspecting day themes, transit directions,
    and activity locations to accurately assign each day's city. Establishes the true
    chronological route sequence of cities visited, route legs, and stays.
    """
    if not isinstance(out_dict, dict):
        return

    days_list = out_dict.get("days", [])
    if not isinstance(days_list, list) or len(days_list) == 0:
        return

    # If raw_cities not provided, extract from cities_visited or days
    if not raw_cities:
        raw_cities = out_dict.get("cities_visited") or []
        if not raw_cities:
            seen_c: list[str] = []
            for d in days_list:
                if isinstance(d, dict) and d.get("city"):
                    c = str(d.get("city")).strip()
                    if c and c not in seen_c:
                        seen_c.append(c)
            if len(seen_c) > 1:
                raw_cities = seen_c

    if not raw_cities or len(raw_cities) <= 1:
        return

    # Build canonical alias lookup
    city_aliases: dict[str, str] = {}
    for c in raw_cities:
        clean = c.strip()
        c_lower = clean.lower()
        city_aliases[c_lower] = clean
        if "nellor" in c_lower:
            city_aliases["nellore"] = clean
            city_aliases["nellor"] = clean
        if "tirupati" in c_lower or "tirumala" in c_lower:
            city_aliases["tirupati"] = clean
            city_aliases["tirumala"] = clean
        if "vijayawada" in c_lower or "bezawada" in c_lower:
            city_aliases["vijayawada"] = clean
            city_aliases["bezawada"] = clean
        if "guntur" in c_lower:
            city_aliases["guntur"] = clean
        if "bengaluru" in c_lower or "bangalore" in c_lower:
            city_aliases["bengaluru"] = clean
            city_aliases["bangalore"] = clean
        if "mysuru" in c_lower or "mysore" in c_lower:
            city_aliases["mysuru"] = clean
            city_aliases["mysore"] = clean
        if "visakhapatnam" in c_lower or "vizag" in c_lower:
            city_aliases["visakhapatnam"] = clean
            city_aliases["vizag"] = clean
        if "varanasi" in c_lower or "kashi" in c_lower or "banaras" in c_lower:
            city_aliases["varanasi"] = clean
            city_aliases["kashi"] = clean
            city_aliases["banaras"] = clean

    # Landmark to City dictionary for precision grounding
    landmark_to_city: dict[str, str] = {
        # Vijayawada landmarks
        "kanaka durga": "vijayawada",
        "undavalli": "vijayawada",
        "prakasam barrage": "vijayawada",
        "bhavani island": "vijayawada",
        "kondapalli": "vijayawada",
        "mangalagiri": "vijayawada",
        "bapu museum": "vijayawada",
        "gunadala": "vijayawada",
        "amaravati": "vijayawada",
        # Nellore landmarks
        "mypadu": "nellore",
        "ranganatha": "nellore",
        "ranganathaswamy": "nellore",
        "jonnawada": "nellore",
        "nelapattu": "nellore",
        "pulicat": "nellore",
        "penna river": "nellore",
        "narasimha swamy temple ghat": "nellore",
        # Tirupati landmarks
        "tirumala": "tirupati",
        "venkateswara": "tirupati",
        "govindaraja": "tirupati",
        "kapila theertham": "tirupati",
        "chandragiri": "tirupati",
        "srikalahasti": "tirupati",
        "padmavathi": "tirupati",
        "alipiri": "tirupati",
        # Visakhapatnam landmarks
        "rk beach": "visakhapatnam",
        "rushikonda": "visakhapatnam",
        "kailasagiri": "visakhapatnam",
        "submarine museum": "visakhapatnam",
        "araku": "visakhapatnam",
        "borra caves": "visakhapatnam",
        "yarada": "visakhapatnam",
        # Goa landmarks
        "calangute": "north goa",
        "baga": "north goa",
        "anjuna": "north goa",
        "vagator": "north goa",
        "chapora": "north goa",
        "fort aguada": "north goa",
        "basilica of bom jesus": "old goa (panjim)",
        "se cathedral": "old goa (panjim)",
        "fontainhas": "old goa (panjim)",
        "palolem": "south goa",
        "agonda": "south goa",
        "colva": "south goa",
        "benaulim": "south goa",
        "cabo de rama": "south goa",
    }

    def _find_city_in_text(text: str) -> str | None:
        if not text:
            return None
        text_lower = text.lower()
        for alias, canonical in city_aliases.items():
            if re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
                return canonical
        return None

    def _find_landmark_in_text(text: str) -> str | None:
        if not text:
            return None
        text_lower = text.lower()
        for lm, target_c in landmark_to_city.items():
            if lm in text_lower:
                for alias, canonical in city_aliases.items():
                    if target_c in alias or alias in target_c:
                        return canonical
        return None

    def _find_transit_dest(text: str) -> str | None:
        if not text:
            return None
        text_lower = text.lower()
        m = re.search(r'(?:travel|head|drive|train|bus|depart)\s+(?:from\s+[a-zA-Z\s]+?\s+)?to\s+([a-zA-Z]+)', text_lower)
        if m:
            dest_word = m.group(1).strip()
            for alias, canonical in city_aliases.items():
                if alias in dest_word or dest_word in alias:
                    return canonical
        m2 = re.search(r'(?:arrive|reaching|reach)\s+(?:at\s+|in\s+)?([a-zA-Z]+)', text_lower)
        if m2:
            dest_word = m2.group(1).strip()
            for alias, canonical in city_aliases.items():
                if alias in dest_word or dest_word in alias:
                    return canonical
        return None

    resolved_cities: list[str] = []
    last_city = raw_cities[0]

    for idx, day_item in enumerate(days_list):
        if not isinstance(day_item, dict):
            continue
        theme = str(day_item.get("theme", ""))
        morning = str(day_item.get("morning", ""))
        afternoon = str(day_item.get("afternoon", ""))
        evening = str(day_item.get("evening", ""))
        night = str(day_item.get("night", ""))
        day_text = f"{theme} {morning} {afternoon} {evening} {night}"

        # 1. Theme exact city match
        city_found = _find_city_in_text(theme)

        # 2. Theme or day landmark match (high precision)
        if not city_found:
            city_found = _find_landmark_in_text(theme)
        if not city_found:
            city_found = _find_landmark_in_text(day_text)

        # 3. Morning transit destination (e.g., "Travel from Tirupati to Nellore")
        if not city_found:
            city_found = _find_transit_dest(morning)

        # 4. Afternoon/Evening/Night text matches
        if not city_found:
            combined_rest = f"{afternoon} {evening} {night}"
            city_found = _find_city_in_text(combined_rest)

        # 5. Morning text general matches
        if not city_found:
            city_found = _find_city_in_text(morning)

        # 6. Check if day_item already had a valid city matching candidate
        if not city_found:
            existing = day_item.get("city")
            if existing:
                for alias, canonical in city_aliases.items():
                    if alias in str(existing).lower():
                        city_found = canonical
                        break

        # 7. Fallback to continuity with previous day
        if not city_found:
            city_found = last_city

        last_city = city_found
        day_item["city"] = city_found
        resolved_cities.append(city_found)

    # Determine sequence of unique cities visited (from day themes or Nearest-Neighbor Corridor)
    ordered_from_days: list[str] = []
    for c in resolved_cities:
        if c not in ordered_from_days:
            ordered_from_days.append(c)

    if len(ordered_from_days) > 1:
        ordered_visited = ordered_from_days
        for c in raw_cities:
            if c not in ordered_visited:
                ordered_visited.append(c)
    else:
        ordered_visited = optimize_city_route(origin_name, raw_cities)
        if not ordered_visited:
            ordered_visited = list(raw_cities)

    out_dict["cities_visited"] = ordered_visited
    out_dict["destination_city"] = ordered_visited[0]


    # Reconcile recommended stays
    stays_list = out_dict.get("recommended_stays") or []
    if not isinstance(stays_list, list):
        stays_list = []
    
    existing_stay_cities = {str(s.get("city", "")).lower() for s in stays_list if isinstance(s, dict) and s.get("city")}
    for c_name in ordered_visited:
        if c_name.lower() not in existing_stay_cities:
            stays_list.append({
                "name": f"Hotel Bliss / Sidhartha ({c_name})",
                "city": c_name,
                "category": "Comfort 3-Star Stay",
                "estimated_price_per_night": round(budget_val * 0.2 / max(1, len(ordered_visited)), 2),
                "address_or_area": f"{c_name} Central Hub",
                "why_recommended": f"Budget-matched accommodation selected for easy access to {c_name} attractions."
            })
    out_dict["recommended_stays"] = stays_list

    # Calculate geographic route legs and corridor distances
    city_seq = [origin_name] + ordered_visited
    route_legs = []
    total_opt_distance = 0.0

    for idx in range(len(city_seq) - 1):
        from_c = city_seq[idx]
        to_c = city_seq[idx + 1]
        coords_from = get_city_coordinates(from_c)
        coords_to = get_city_coordinates(to_c)

        if coords_from and coords_to:
            leg_km = calculate_distance_km(coords_from, coords_to)
        else:
            leg_km = 120.0 + (idx * 40.0)
        total_opt_distance += leg_km

        # Realistic duration & transit recommendation based on distance
        if leg_km <= 50:
            dur_str = f"~45 mins ({leg_km:.0f} km)"
            transit_opt = f"Local Intercity Express Train / APSRTC Express ({from_c} to {to_c})"
        elif leg_km <= 150:
            dur_str = f"~2 - 2.5 hrs ({leg_km:.0f} km)"
            transit_opt = f"Superfast Express Train / State Express Bus ({from_c} to {to_c})"
        elif leg_km <= 300:
            dur_str = f"~3.5 - 4.5 hrs ({leg_km:.0f} km)"
            transit_opt = f"Vande Bharat / Intercity Express Train ({from_c} to {to_c})"
        else:
            dur_str = f"~5 - 7 hrs ({leg_km:.0f} km)"
            transit_opt = f"Express Rail / Overnight Sleeper Bus ({from_c} to {to_c})"

        if idx == 0:
            proximity_badge = "Nearest Adjacent First ✅"
        elif idx == len(city_seq) - 2:
            proximity_badge = "Farthest Final Stop 🏁"
        else:
            proximity_badge = "Corridor Progression 🚆"

        route_legs.append({
            "leg_number": idx + 1,
            "from_city": from_c,
            "to_city": to_c,
            "route_title": f"{from_c} ➔ {to_c}",
            "distance_km": leg_km,
            "travel_duration": dur_str,
            "proximity_badge": proximity_badge,
            "mode": "Train / Bus",
            "recommended_option": transit_opt,
            "estimated_cost_per_person": round(max(80.0, leg_km * 1.5), 2),
            "why_recommended": f"Optimized corridor leg connecting {from_c} to {to_c} with zero backtrack delay.",
            "local_connect_tips": f"Auto-rickshaws and app cabs available at {to_c} arrival terminal."
        })

    # Compute unoptimized distance (if traveler had visited raw_cities in input order)
    unopt_seq = [origin_name] + [c for c in raw_cities if c.lower() != origin_name.lower()]
    unopt_distance = 0.0
    for i in range(len(unopt_seq) - 1):
        c1 = get_city_coordinates(unopt_seq[i])
        c2 = get_city_coordinates(unopt_seq[i + 1])
        if c1 and c2:
            unopt_distance += calculate_distance_km(c1, c2)
        else:
            unopt_distance += 200.0

    dist_saved = max(0.0, round(unopt_distance - total_opt_distance, 1))
    time_saved_hrs = round(dist_saved / 55.0, 1) if dist_saved > 0 else 0.0

    if origin_name and origin_name.lower() != "origin":
        out_dict["origin_city"] = origin_name

    out_dict["route_analysis"] = {
        "start_hub": origin_name,
        "optimized_sequence": city_seq,
        "total_distance_km": round(total_opt_distance, 1),
        "unoptimized_distance_km": round(unopt_distance, 1),
        "distance_saved_km": dist_saved,
        "time_saved_hours": time_saved_hrs,
        "legs": route_legs,
        "corridor_summary": (
            f"Optimal route starts at {origin_name}, visiting nearest adjacent hub ({ordered_visited[0]}) first "
            f"and progressing sequentially to {ordered_visited[-1]}, saving {dist_saved:.0f} km "
            f"and ~{time_saved_hrs} hours of unnecessary backtracking!"
        ) if dist_saved > 0 else f"Direct geographic route linking {origin_name} to {ordered_visited[0]}."
    }

    inter_transit_raw = out_dict.get("intercity_transport")
    inter_transit = inter_transit_raw if isinstance(inter_transit_raw, dict) else {
        "mode": "Train / Bus",
        "recommended_option": f"Multi-City Route Transit ({' ➔ '.join(city_seq)})",
        "estimated_cost_per_person": sum(leg["estimated_cost_per_person"] for leg in route_legs),
        "travel_duration": "Multi-leg journey",
        "why_recommended": "Optimized sequential transit linking all target destinations.",
        "local_connect_tips": "Local auto-rickshaws and cabs available at each transit station."
    }
    inter_transit["route_legs"] = route_legs
    inter_transit["recommended_option"] = f"Multi-City Route Transit ({' ➔ '.join(city_seq)})"
    out_dict["intercity_transport"] = inter_transit



def _run_crew_sync(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Executes trip planning in a worker thread:
    - Multi-city trips: Dispatches to the Orchestrator-Workers pipeline (concurrent city workers & synthesis)
    - Single-city trips: Bypasses orchestrator and runs standard crew pipeline with evaluator loop
    """
    from trip_planner.patterns.orchestrator import TripOrchestrator

    if TripOrchestrator.should_use_orchestrator(inputs):
        logger.info(f"[_run_crew_sync] Multi-city request detected. Executing Orchestrator-Workers pipeline for: {inputs.get('cities')}")
        orchestrator = TripOrchestrator()
        multi_itinerary = orchestrator.orchestrate_itinerary(inputs)
        out_dict = multi_itinerary.model_dump()
        out_dict["orchestrator_used"] = True
    else:
        logger.info("[_run_crew_sync] Single-city request detected. Executing standard crew pipeline with evaluator loop.")
        from trip_planner.crew import TripPlannerCrew
        crew_instance = TripPlannerCrew()
        out_dict = crew_instance.run_with_evaluator_loop(inputs=inputs)
        if isinstance(out_dict, dict):
            out_dict["orchestrator_used"] = False

    if isinstance(out_dict, dict):
        # Store origin_city from inputs if available
        orig_val = inputs.get("origin")
        if orig_val and str(orig_val).strip() and str(orig_val).strip().lower() != "origin":
            out_dict["origin_city"] = str(orig_val).strip()

        if "travelers" in inputs:
            req_travelers = int(inputs.get("travelers", 1))
            out_dict["travelers"] = req_travelers
            tot_cost = clean_float(out_dict.get("total_estimated_cost"), 0.0)
            out_dict["cost_per_person"] = round(tot_cost / max(1, req_travelers), 2)

        # Multi-city normalization & strict single vs multi-city handling
        user_cities_str = str(inputs.get("cities", "")).strip()
        user_city_list = [c.strip() for c in user_cities_str.split(",") if c.strip()]
        is_multi_req = bool(inputs.get("multi_city")) and len(user_city_list) > 1

        if not is_multi_req and len(user_city_list) == 1:
            # Single-destination trip: strictly enforce ONLY the user's requested destination city
            target_city = user_city_list[0]
            out_dict["destination_city"] = target_city
            out_dict["cities_visited"] = None
            out_dict["route_analysis"] = None

            # Ensure all days belong exclusively to target_city
            days_list = out_dict.get("days", [])
            if isinstance(days_list, list):
                for day in days_list:
                    if isinstance(day, dict):
                        day["city"] = target_city

            # Ensure intercity transit only connects Origin -> Target City (zero multi-city route legs)
            origin_name = str(inputs.get("origin", "Origin")).strip()
            inter_transit = out_dict.get("intercity_transport")
            if not isinstance(inter_transit, dict):
                inter_transit = {}
            inter_transit["route_legs"] = []
            if origin_name.lower() != target_city.lower():
                inter_transit["recommended_option"] = f"APSRTC Bus or Express Train ({origin_name} to {target_city})"
                inter_transit["why_recommended"] = f"{target_city} is the primary destination. Direct transit connecting {origin_name} to {target_city}."
                inter_transit["travel_duration"] = inter_transit.get("travel_duration") if (inter_transit.get("travel_duration") and "N/A" not in inter_transit.get("travel_duration", "")) else "Direct journey"
            else:
                inter_transit["recommended_option"] = f"Local Transit in {target_city}"
                inter_transit["why_recommended"] = f"Trip is based locally in {target_city}."
            out_dict["intercity_transport"] = inter_transit

            # Ensure all stays belong to target_city
            stays = out_dict.get("recommended_stays")
            if isinstance(stays, list):
                for s in stays:
                    if isinstance(s, dict):
                        s["city"] = target_city
        elif is_multi_req:
            origin_name = str(inputs.get("origin", "Origin")).strip()
            budget_val = clean_float(inputs.get("budget"), 25000.0)
            reconcile_multi_city_itinerary(out_dict, raw_cities=user_city_list, origin_name=origin_name, budget_val=budget_val)
        else:
            out_dict["cities_visited"] = None
            if isinstance(out_dict.get("intercity_transport"), dict):
                out_dict["intercity_transport"]["route_legs"] = []

        # Date processing & multi-format date parser
        raw_date = inputs.get("travel_date")
        ret_date = inputs.get("return_date")
        if raw_date and isinstance(raw_date, str) and raw_date.strip():
            try:
                from datetime import datetime, timedelta

                def _parse_dt(d_str):
                    if not d_str or not isinstance(d_str, str):
                        return None
                    s = d_str.strip()
                    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
                        try:
                            return datetime.strptime(s, fmt)
                        except ValueError:
                            pass
                    return None

                start_dt = _parse_dt(raw_date)
                if start_dt:
                    out_dict["start_date"] = start_dt.strftime("%Y-%m-%d")
                    out_dict["travel_date"] = start_dt.strftime("%Y-%m-%d")
                    days_list = out_dict.get("days", [])
                    if isinstance(days_list, list):
                        for idx, day_item in enumerate(days_list):
                            if isinstance(day_item, dict):
                                curr_dt = start_dt + timedelta(days=idx)
                                day_item["date"] = curr_dt.strftime("%d %b %Y")
                        
                        end_dt = _parse_dt(ret_date) if ret_date else None
                        if not end_dt:
                            end_dt = start_dt + timedelta(days=max(0, len(days_list) - 1))
                        out_dict["end_date"] = end_dt.strftime("%Y-%m-%d")
            except Exception as e:
                print(f"Date formatting error: {e}")

        # Deterministic Budget Validation: Surface honest warning if initial estimate exceeds requested budget by >5%
        user_budget = inputs.get("budget")
        if user_budget is not None:
            try:
                target_budget = clean_float(user_budget, 0.0)
                tot_cost = clean_float(out_dict.get("total_estimated_cost"), 0.0)
                currency = str(out_dict.get("currency") or inputs.get("currency") or "INR").strip()
                sym = "₹" if currency == "INR" else ("$" if currency == "USD" else ("€" if currency == "EUR" else f"{currency} "))

                if target_budget > 0 and tot_cost > (target_budget * 1.05):
                    overrun = tot_cost - target_budget
                    pct = (overrun / target_budget) * 100.0
                    warning_msg = (
                        f"⚠️ Budget Alert: This itinerary's estimated cost ({sym}{tot_cost:,.0f}) "
                        f"exceeds your requested budget ({sym}{target_budget:,.0f}) by {sym}{overrun:,.0f} ({pct:.1f}%)."
                    )
                    out_dict["budget_exceeded_warning"] = warning_msg
                    out_dict["budget_alert"] = warning_msg
                else:
                    out_dict["budget_exceeded_warning"] = None
                    out_dict["budget_alert"] = None
            except Exception as e:
                print(f"Budget check error: {e}")

    return out_dict


def _run_revision_sync(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Executes the specialized single-agent revision crew in a synchronous worker thread.
    """
    from trip_planner.crew import TripPlannerCrew

    crew_instance = TripPlannerCrew().revision_crew()
    result = crew_instance.kickoff(inputs=inputs)

    if hasattr(result, "pydantic") and result.pydantic:
        return result.pydantic.model_dump()
    elif hasattr(result, "raw"):
        try:
            return json.loads(result.raw)
        except Exception:
            return {"raw_output": result.raw}
    return {"raw_output": str(result)}


async def _execute_trip_job(job_id: str, inputs: dict[str, Any]) -> None:
    """
    Background worker task running the CrewAI pipeline and storing results.
    Runs strictly through the real 3-agent AI pipeline without synthetic fallbacks.
    """
    db.update_job(job_id, status="running")
    try:
        # Give CrewAI up to 900 seconds (15 minutes) to complete the multi-agent pipeline with live web searches and rate limit backoffs
        itinerary_data = await asyncio.wait_for(asyncio.to_thread(_run_crew_sync, inputs), timeout=900.0)
        db.update_job(job_id, status="complete", result=itinerary_data)
    except asyncio.TimeoutError:
        logger.error(f"[_execute_trip_job] CrewAI pipeline execution timed out after 900s for job {job_id}")
        db.update_job(job_id, status="failed", error="AI Trip Planning timed out after 900 seconds due to rate limit backoffs. Please try again.")
    except Exception as e:
        err_text = str(e) or repr(e)
        logger.error(f"[_execute_trip_job] CrewAI pipeline execution failed: {err_text}")
        db.update_job(job_id, status="failed", error=f"AI Trip Planning failed: {err_text}")


async def _execute_revision_job(job_id: str, inputs: dict[str, Any]) -> None:
    """
    Background worker task running the single-agent revision task and storing results.
    Computes deterministic budget-overrun alert when revised cost exceeds original cost.
    """
    db.update_job(job_id, status="running")
    try:
        orig_job = db.get_job(job_id)
        orig_cost = 0.0
        orig_origin = None
        if orig_job and isinstance(orig_job.get("result"), dict):
            orig_cost = float(orig_job["result"].get("total_estimated_cost", 0.0))
            orig_origin = orig_job["result"].get("origin_city")

        itinerary_data = await asyncio.to_thread(_run_revision_sync, inputs)

        if isinstance(itinerary_data, dict):
            if orig_origin and not itinerary_data.get("origin_city"):
                itinerary_data["origin_city"] = orig_origin

            new_cost = float(itinerary_data.get("total_estimated_cost", 0.0))
            currency = itinerary_data.get("currency", "INR")
            sym = "$" if currency == "USD" else ("€" if currency == "EUR" else "₹")

            budget_alert = None
            if orig_cost > 0 and new_cost > orig_cost:
                diff = round(new_cost - orig_cost, 2)
                pct = round((diff / orig_cost) * 100.0, 1)
                budget_alert = f"This revision increased your total cost from {sym}{int(orig_cost):,} to {sym}{int(new_cost):,} (+{sym}{int(diff):,}, +{pct:.1f}%)"

            itinerary_data["budget_alert"] = budget_alert

        db.update_job(job_id, status="complete", result=itinerary_data)
    except Exception as e:
        db.update_job(job_id, status="failed", error=str(e))


def _run_qa_sync(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Executes the specialized single-agent destination Q&A crew in a worker thread.
    """
    from trip_planner.crew import TripPlannerCrew

    crew_instance = TripPlannerCrew().qa_crew()
    result = crew_instance.kickoff(inputs=inputs)

    grounded_claims: list[str] = []
    ungrounded_claims: list[str] = []
    answer_text = ""
    sources: list[str] | None = None

    if hasattr(result, "pydantic") and result.pydantic:
        pydantic_res = result.pydantic
        if isinstance(pydantic_res, QAResponse):
            answer_text = pydantic_res.answer
            grounded_claims = pydantic_res.grounded_claims or []
            ungrounded_claims = pydantic_res.ungrounded_claims or []
            sources = pydantic_res.sources
        elif isinstance(pydantic_res, dict):
            answer_text = pydantic_res.get("answer", "")
            grounded_claims = pydantic_res.get("grounded_claims", [])
            ungrounded_claims = pydantic_res.get("ungrounded_claims", [])
            sources = pydantic_res.get("sources")
    elif hasattr(result, "json_dict") and result.json_dict:
        answer_text = result.json_dict.get("answer", "")
        grounded_claims = result.json_dict.get("grounded_claims", [])
        ungrounded_claims = result.json_dict.get("ungrounded_claims", [])
        sources = result.json_dict.get("sources")
    else:
        raw_text = result.raw if hasattr(result, "raw") else str(result)
        try:
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\n", "", cleaned)
                cleaned = re.sub(r"\n```$", "", cleaned)
            data = json.loads(cleaned)
            if isinstance(data, dict):
                answer_text = data.get("answer", raw_text)
                grounded_claims = data.get("grounded_claims", [])
                ungrounded_claims = data.get("ungrounded_claims", [])
                sources = data.get("sources")
            else:
                answer_text = raw_text.strip()
        except Exception:
            answer_text = raw_text.strip()

    if not sources:
        raw_text = result.raw if hasattr(result, "raw") else str(result)
        urls = re.findall(r"https?://[^\s\)\],\"']+", raw_text)
        sources = list(dict.fromkeys(urls)) if urls else None

    return {
        "answer": answer_text,
        "grounded_claims": grounded_claims,
        "ungrounded_claims": ungrounded_claims,
        "sources": sources,
    }


async def _execute_qa_job(
    job_id: str,
    inputs: dict[str, Any],
    root_job_id: str,
    question: str,
) -> None:
    """
    Background worker task running the destination Q&A crew and storing results.
    """
    db.update_job(job_id, status="running")
    try:
        qa_data = await asyncio.to_thread(_run_qa_sync, inputs)
        qa_exchange = {
            "question": question,
            "answer": qa_data.get("answer", ""),
            "timestamp": time.time(),
            "grounded_claims": qa_data.get("grounded_claims", []),
            "ungrounded_claims": qa_data.get("ungrounded_claims", []),
        }

        root_job = db.get_job(root_job_id)
        current_history = root_job.get("qa_history", []) if root_job else []
        updated_history = current_history + [qa_exchange]
        db.update_job(root_job_id, qa_history=updated_history)

        qa_data["qa_history"] = updated_history
        db.update_job(job_id, status="complete", result=qa_data)
    except Exception as e:
        db.update_job(job_id, status="failed", error=str(e))


def _get_current_user_email(request: Request) -> str | None:
    token = request.cookies.get("session_token")
    auth_header = request.headers.get("Authorization")
    if not token and auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    return db.get_session_email(token)


def _generate_itinerary_pdf(job_id: str, itinerary: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f766e"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    bold_body = ParagraphStyle(
        "BoldBody",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    city = itinerary.get("destination_city", "Trip")
    country = itinerary.get("destination_country", "")
    days_count = itinerary.get("trip_length_days", 1)
    currency = itinerary.get("currency", "INR")
    total_cost = itinerary.get("total_estimated_cost", 0)

    # Title Banner
    story.append(Paragraph(f"Travel Itinerary: {city}, {country}", title_style))
    story.append(Paragraph(f"Duration: {days_count} Day(s) | Total Estimated Budget: {currency} {total_cost:,.2f}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=10))

    # Day-by-Day Itinerary
    story.append(Paragraph("Day-by-Day Schedule", heading_style))
    days = itinerary.get("days", [])
    for day in days:
        day_num = day.get("day_number", 1)
        theme = day.get("theme", "")
        cost = day.get("estimated_cost", 0)
        morning = day.get("morning", "")
        afternoon = day.get("afternoon", "")
        evening = day.get("evening", "")
        cost_items = day.get("cost_breakdown", [])

        day_title = f"Day {day_num}: {theme} ({currency} {cost:,.2f})"
        story.append(Paragraph(day_title, ParagraphStyle("DayTitle", parent=heading_style, fontSize=11, leading=14, textColor=colors.HexColor("#0284c7"))))

        table_data = [
            [Paragraph("<b>Morning</b>", bold_body), Paragraph(morning, body_style)],
            [Paragraph("<b>Afternoon</b>", bold_body), Paragraph(afternoon, body_style)],
            [Paragraph("<b>Evening</b>", bold_body), Paragraph(evening, body_style)],
        ]
        if cost_items:
            breakdown_lines = []
            for item in cost_items:
                i_name = item.get("item") if isinstance(item, dict) else getattr(item, "item", "")
                i_amt = item.get("amount") if isinstance(item, dict) else getattr(item, "amount", 0)
                breakdown_lines.append(f"• {i_name}: {currency} {i_amt:,.2f}")
            breakdown_str = "<br/>".join(breakdown_lines)
            table_data.append([Paragraph("<b>Cost Items</b>", bold_body), Paragraph(breakdown_str, body_style)])

        t = Table(table_data, colWidths=[80, 460])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#f8fafc")),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    # Packing Suggestions
    packing = itinerary.get("packing_suggestions", [])
    if packing:
        story.append(Paragraph("Packing Suggestions", heading_style))
        pack_text = "<br/>".join([f"• {item}" for item in packing])
        story.append(Paragraph(pack_text, body_style))
        story.append(Spacer(1, 8))

    # Transit Advice
    transit = itinerary.get("local_transport_advice", [])
    if transit:
        story.append(Paragraph("Local Transit Advice", heading_style))
        transit_text = "<br/>".join([f"• {item}" for item in transit])
        story.append(Paragraph(transit_text, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


@app.get("/my-trips")
@app.get("/my-trips.html")
async def serve_my_trips():
    my_trips_file = FRONTEND_DIR / "my-trips.html"
    if my_trips_file.exists():
        return FileResponse(str(my_trips_file))
    raise HTTPException(status_code=404, detail="my-trips.html not found")


@app.get("/share")
@app.get("/share.html")
async def serve_share():
    share_file = FRONTEND_DIR / "share.html"
    if share_file.exists():
        return FileResponse(str(share_file))
    raise HTTPException(status_code=404, detail="share.html not found")


@app.get("/api/trip/{job_id}/share")
async def get_shareable_trip(job_id: str):
    """
    Public, read-only endpoint for sharing completed itineraries.
    Returns 404 for nonexistent, pending, running, or failed jobs.
    Strips user_email, qa_history, and internal job metadata.
    """
    job = db.get_job(job_id)
    if not job or job.get("status") != "complete":
        raise HTTPException(
            status_code=404,
            detail="Shared trip itinerary not found or processing is not complete.",
        )

    result = job.get("result")
    if not result or not isinstance(result, dict):
        raise HTTPException(status_code=404, detail="Itinerary data is unavailable.")

    # Explicitly clean and ensure strictly public TripItinerary fields
    if isinstance(result, dict) and result.get("cities_visited") and isinstance(result["cities_visited"], list) and len(result["cities_visited"]) > 1:
        reconcile_multi_city_itinerary(result)

    clean_itinerary = {
        "destination_city": result.get("destination_city"),
        "origin_city": result.get("origin_city"),
        "cities_visited": result.get("cities_visited"),
        "destination_country": result.get("destination_country"),
        "trip_length_days": result.get("trip_length_days"),
        "currency": result.get("currency", "INR"),
        "total_estimated_cost": result.get("total_estimated_cost"),
        "days": result.get("days", []),
        "packing_suggestions": result.get("packing_suggestions", []),
        "local_transport_advice": result.get("local_transport_advice", []),
        "recommended_stay": result.get("recommended_stay"),
        "budget_upgrade_insights": result.get("budget_upgrade_insights"),
    }
    return clean_itinerary



@app.post("/api/auth/request-login")
@limiter.limit("30/hour")
async def request_login_endpoint(request: Request, payload: LoginRequest):
    raw_email = payload.email.strip().lower()
    if "@" not in raw_email or "." not in raw_email:
        raise HTTPException(status_code=400, detail="Invalid email address format.")

    token = db.create_login_token(raw_email)
    base_str = str(request.base_url).rstrip("/")
    if "0.0.0.0" in base_str:
        base_str = base_str.replace("0.0.0.0", "127.0.0.1")

    app_url_env = os.getenv("APP_URL")
    if app_url_env:
        base_str = app_url_env.rstrip("/")

    verify_url = f"{base_str}/api/auth/verify?token={token}"

    resend_key = os.getenv("RESEND_API_KEY")
    email_sent = False
    if resend_key:
        resend.api_key = resend_key
        try:
            email_html = f'''
            <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 500px; border: 1px solid #e0e0e0; border-radius: 8px;">
              <h2 style="color: #4f46e5;">✈️ AI Trip Planner Sign In</h2>
              <p>Click the link below to sign in to your AI Trip Planner account:</p>
              <p style="margin: 20px 0;">
                <a href="{verify_url}" style="background-color: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Sign In to AI Trip Planner</a>
              </p>
              <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
              <p style="font-size: 14px; color: #374151;"><strong>Opened email on mobile or another browser?</strong></p>
              <p style="font-size: 13px; color: #4b5563;">Copy and paste this Token into the login screen on your PC:</p>
              <div style="background: #f3f4f6; padding: 10px; border-radius: 6px; font-family: monospace; word-break: break-all; font-weight: bold; color: #1f2937; margin: 10px 0;">{token}</div>
              <p style="font-size: 12px; color: #6b7280; margin-top: 15px;">This magic link & token expire in 15 minutes.</p>
            </div>
            '''
            resend.Emails.send({
                "from": "AI Trip Planner <onboarding@resend.dev>",
                "to": [raw_email],
                "subject": "Magic Link Sign In for AI Trip Planner",
                "html": email_html,
            })
            email_sent = True
        except Exception as e:
            logger.error(f"Failed to dispatch magic link email via Resend API: {e}")

    if not email_sent:
        logger.warning(
            "\n" + "=" * 80 +
            "\n[SECURITY WARNING] RESEND_API_KEY is NOT configured properly or email delivery failed!\n" +
            "Magic login link printed to server console FOR LOCAL DEVELOPMENT ONLY.\n" +
            f"MAGIC LOGIN LINK FOR {raw_email}: {verify_url}\n" +
            f"MAGIC TOKEN FOR {raw_email}: {token}\n" +
            "=" * 80 + "\n"
        )
        print(f"\n[MAGIC LINK FOR {raw_email}]: {verify_url}\n", flush=True)

    msg = "A magic login link has been sent! Please check your email inbox." if email_sent else "A magic login link has been sent to server logs (local mode). Click below to sign in."

    return {
        "message": msg,
        "email_sent": email_sent,
        "token": token,
        "verify_url": verify_url if not email_sent else None,
    }


@app.get("/api/auth/verify")
async def verify_login_endpoint(token: str):
    email = db.verify_and_consume_login_token(token)
    if not email:
        return RedirectResponse(url="/?auth_error=invalid_or_expired_token", status_code=303)

    session_token = db.create_session(email)
    response = RedirectResponse(url="/my-trips", status_code=303)
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/api/auth/verify-token")
async def verify_token_endpoint(payload: VerifyTokenRequest):
    raw_token = payload.token.strip()
    if "token=" in raw_token:
        raw_token = raw_token.split("token=")[-1].split("&")[0].strip()

    email = db.verify_and_consume_login_token(raw_token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired magic token. Please request a new one.")

    session_token = db.create_session(email)
    response = JSONResponse({"message": "Successfully authenticated!", "email": email})
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.get("/api/auth/me")
async def auth_me_endpoint(request: Request):
    email = _get_current_user_email(request)
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"email": email}


@app.post("/api/auth/logout")
async def logout_endpoint(request: Request):
    cookie_token = request.cookies.get("session_token")
    auth_header = request.headers.get("Authorization")
    token = cookie_token
    if not token and auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if token:
        db.delete_session(token)

    response = JSONResponse({"message": "Successfully logged out"})
    response.delete_cookie(key="session_token", path="/")
    return response


@app.get("/api/my-trips")
async def get_my_trips_endpoint(request: Request):
    email = _get_current_user_email(request)
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    trips = db.get_user_jobs(email)
    return {"email": email, "trips": trips}


@app.get("/api/trip/{job_id}/pdf")
async def export_trip_pdf_endpoint(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trip job not found")
    if job.get("status") != "complete" or not job.get("result"):
        raise HTTPException(status_code=400, detail="Cannot export PDF for an incomplete or failed trip job")

    pdf_bytes = _generate_itinerary_pdf(job_id, job["result"])
    city_slug = job["result"].get("destination_city", "itinerary").lower().replace(" ", "_")
    filename = f"trip_itinerary_{city_slug}_{job_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _generate_itinerary_ics(job_id: str, itinerary: dict[str, Any]) -> bytes:
    """
    Builds a standard RFC 5545 iCalendar (.ics) file containing scheduled daily itinerary events.
    Compatible with Google Calendar, Apple Calendar, and Outlook.
    """
    from datetime import datetime, timedelta

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AI Trip Planner//Trip Itinerary//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Trip to {itinerary.get('destination_city', 'Destination')}",
    ]

    # Parse start date or default to tomorrow
    start_date_str = itinerary.get("start_date") or itinerary.get("travel_date")
    start_dt = None
    if start_date_str:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                start_dt = datetime.strptime(start_date_str.strip(), fmt)
                break
            except ValueError:
                pass
    if not start_dt:
        start_dt = datetime.now() + timedelta(days=1)

    now_utc_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    days = itinerary.get("days", [])
    city_name = itinerary.get("destination_city", "Destination")

    for idx, day in enumerate(days):
        if not isinstance(day, dict):
            continue
        curr_dt = start_dt + timedelta(days=idx)
        date_prefix = curr_dt.strftime("%Y%m%d")
        day_num = day.get("day_number", idx + 1)
        theme = day.get("theme", f"Day {day_num}")
        day_city = day.get("city", city_name)

        slots = [
            ("Morning", "090000", "120000", day.get("morning")),
            ("Afternoon", "130000", "170000", day.get("afternoon")),
            ("Evening", "180000", "210000", day.get("evening")),
        ]

        for slot_name, t_start, t_end, activity_desc in slots:
            if not activity_desc:
                continue
            clean_desc = str(activity_desc).replace("\n", " ").replace("\r", " ").replace(";", "\\;").replace(",", "\\,")
            summary = f"Day {day_num} {slot_name}: {theme}"
            uid = f"trip-{job_id[:8]}-day{day_num}-{slot_name.lower()}@tripplanner.ai"

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_utc_str}",
                f"DTSTART:{date_prefix}T{t_start}",
                f"DTEND:{date_prefix}T{t_end}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{clean_desc}",
                f"LOCATION:{day_city}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode("utf-8")


@app.get("/api/trip/{job_id}/calendar.ics")
async def export_trip_calendar_endpoint(job_id: str):
    """
    Generates and exports standard RFC 5545 iCalendar (.ics) format for Google/Apple Calendar.
    """
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trip job not found")
    if job.get("status") != "complete" or not job.get("result"):
        raise HTTPException(status_code=400, detail="Cannot export Calendar for an incomplete or failed trip job")

    ics_bytes = _generate_itinerary_ics(job_id, job["result"])
    city_slug = job["result"].get("destination_city", "trip").lower().replace(" ", "_")
    filename = f"trip_{city_slug}_{job_id[:8]}.ics"
    return Response(
        content=ics_bytes,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/calendar; charset=utf-8",
        },
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify server and API key status."""
    has_api_key = bool(os.getenv("GROQ_API_KEY"))
    return {
        "status": "ok",
        "service": "AI Trip Planner API",
        "version": "0.1.0",
        "groq_configured": has_api_key,
        "default_model": os.getenv("TRIP_PLANNER_MODEL", "groq/openai/gpt-oss-120b"),
    }


class CompareTripsRequest(BaseModel):
    job_ids: list[str] = Field(..., description="List of 2 to 3 completed job IDs to compare")


@app.post("/api/plan-trip", response_model=JobStatusResponse)
@limiter.limit("30/minute")
async def plan_trip_endpoint(request: Request, payload: TripPlanRequest):
    """
    Accepts trip parameters, initializes an async background job,
    and immediately returns a job_id for status polling.
    """
    raw_mode = (payload.travel_mode or "").strip().lower()
    mode = raw_mode if raw_mode else "domestic"

    # Allowlist gate: Phase 1 strictly accepts domestic Indian travel
    if mode != "domestic":
        raise HTTPException(
            status_code=400,
            detail=(
                "Global destination planning is scheduled for Phase 2. "
                "Phase 1 is strictly customized for domestic Indian travel (INR)."
            ),
        )

    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not configured in the environment or .env file.",
        )

    # Fetch weather forecast with explicit error resiliency
    weather_forecast_str = "Weather data unavailable (seasonal weather guidelines apply)."
    try:
        primary_city = payload.cities.split(",")[0].strip()
        fc_list = get_forecast(primary_city, payload.trip_length)
        if fc_list:
            weather_forecast_str = format_forecast_summary(fc_list)
    except Exception as e:
        logger.warning(
            f"Weather forecast lookup failed for city '{payload.cities}': {e}. Using generic seasonal fallback."
        )

    crew_inputs = {
        "origin": payload.origin.strip(),
        "cities": payload.cities.strip(),
        "interests": payload.interests.strip(),
        "trip_length": str(payload.trip_length),
        "budget": f"₹{payload.budget:,.0f} {payload.currency}" if payload.currency == "INR" else f"{payload.currency} {payload.budget:,.0f}",
        "currency": payload.currency,
        "travelers": str(payload.travelers),
        "weather_forecast": weather_forecast_str,
        "language": payload.language,
        "travel_date": payload.travel_date,
        "return_date": payload.return_date,
        "multi_city": payload.multi_city,
    }

    user_email = _get_current_user_email(request)
    job_id = str(uuid.uuid4())
    job_rec = db.create_job(
        job_id=job_id,
        job_type="plan",
        status="pending",
        user_email=user_email,
        travel_date=payload.travel_date,
    )

    # Kick off asynchronous background execution
    asyncio.create_task(_execute_trip_job(job_id, crew_inputs))

    return JobStatusResponse(
        job_id=job_id,
        status="pending",
        created_at=job_rec["created_at"],
        travel_date=job_rec.get("travel_date"),
        reminder_sent=job_rec.get("reminder_sent"),
    )


def _is_rain_day(day: dict[str, Any], threshold: float = 50.0) -> bool:
    """
    Determines if a day should be counted as a 'rain day' based on numeric rain probability (>50%).
    Checks:
    1. Direct numeric 'rain_probability' or 'precipitation_probability' in day dictionary.
    2. Explicit numeric percentage in free-text 'weather_note' (e.g. '22% rain' -> 22.0, '71%' -> 71.0).
    3. Fallback to qualitative rain terms ONLY if no numeric percentage is present anywhere.
    """
    for key in ("rain_probability", "precipitation_probability"):
        val = day.get(key)
        if val is not None:
            try:
                return float(val) > threshold
            except (ValueError, TypeError):
                pass

    wnote = day.get("weather_note") or ""
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", wnote)
    if match:
        try:
            prob = float(match.group(1))
            return prob > threshold
        except ValueError:
            pass

    wnote_lower = wnote.lower()
    if any(k in wnote_lower for k in ("heavy rain", "thunderstorm", "downpour", "rain likely", "showers", "drizzle", "rain")):
        if not any(neg in wnote_lower for neg in ("no rain", "0%", "clear", "sunny", "low chance")):
            return True

    return False


@app.post("/api/compare-trips")
async def compare_trips_endpoint(payload: CompareTripsRequest):
    """
    Accepts 2 to 3 completed job_ids and returns a structural comparison summary
    (destination, costs, travelers, cost_per_person, trip length, and weather summary).
    Does NOT require LLM execution.
    """
    if not payload.job_ids or len(payload.job_ids) < 2 or len(payload.job_ids) > 3:
        raise HTTPException(
            status_code=400,
            detail="Comparison requires between 2 and 3 job IDs.",
        )

    comparisons = []
    for jid in payload.job_ids:
        job = db.get_job(jid)
        if not job:
            raise HTTPException(status_code=404, detail=f"Trip job '{jid}' not found.")
        if job.get("status") != "complete" or not job.get("result"):
            raise HTTPException(status_code=400, detail=f"Trip job '{jid}' is not complete.")

        res = job["result"]
        days = res.get("days", [])
        rain_days_count = sum(1 for d in days if _is_rain_day(d))

        if rain_days_count == 0:
            w_summary = "Mostly clear / pleasant"
        else:
            w_summary = f"Rain likely on {rain_days_count} of {len(days)} days"

        total_cost = res.get("total_estimated_cost", 0.0)
        travelers_cnt = res.get("travelers", 1)
        cost_pp = res.get("cost_per_person", round(total_cost / max(1, travelers_cnt), 2))

        comparisons.append({
            "job_id": jid,
            "destination_city": res.get("destination_city", "Unknown"),
            "destination_country": res.get("destination_country", "India"),
            "trip_length_days": res.get("trip_length_days", 1),
            "currency": res.get("currency", "INR"),
            "total_estimated_cost": total_cost,
            "cost_per_person": cost_pp,
            "travelers": travelers_cnt,
            "weather_summary": w_summary,
        })

    return {"comparison": comparisons}



@app.post("/api/revise-trip", response_model=JobStatusResponse)
@limiter.limit("10/hour")
async def revise_trip_endpoint(request: Request, payload: RevisionRequest):
    """
    Accepts follow-up feedback on an existing completed itinerary,
    spawns a targeted single-agent revision task, and returns a new job_id.
    """
    orig_job = db.get_job(payload.job_id)
    if not orig_job:
        raise HTTPException(status_code=404, detail="Original job not found")

    if orig_job.get("status") != "complete" or not orig_job.get("result"):
        raise HTTPException(
            status_code=400,
            detail="Cannot revise a job that has not completed successfully",
        )

    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not configured in the environment or .env file.",
        )

    orig_itinerary = orig_job["result"]
    itinerary_str = json.dumps(orig_itinerary, indent=2) if isinstance(orig_itinerary, dict) else str(orig_itinerary)

    revision_inputs = {
        "itinerary": itinerary_str,
        "feedback": payload.feedback.strip(),
        "language": payload.language,
    }

    new_job_id = str(uuid.uuid4())
    job_rec = db.create_job(
        job_id=new_job_id,
        job_type="revise",
        status="pending",
        parent_job_id=payload.job_id,
    )

    asyncio.create_task(_execute_revision_job(new_job_id, revision_inputs))

    return JobStatusResponse(
        job_id=new_job_id,
        status="pending",
        created_at=job_rec["created_at"],
    )


@app.post("/api/ask-question", response_model=JobStatusResponse)
@limiter.limit("15/hour")
async def ask_question_endpoint(request: Request, payload: DestinationQuestion):
    """
    Accepts a direct question about a destination from an existing completed job,
    spawns a targeted single-agent Q&A task, and returns a job_id for status polling.
    """
    orig_job = db.get_job(payload.job_id)
    if not orig_job:
        raise HTTPException(status_code=404, detail="Original job not found")

    if orig_job.get("status") != "complete" or not orig_job.get("result"):
        raise HTTPException(
            status_code=400,
            detail="Cannot ask questions about a job that has not completed successfully",
        )

    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not configured in the environment or .env file.",
        )

    orig_result = orig_job["result"]
    destination_city = "the destination"
    if isinstance(orig_result, dict):
        destination_city = (
            orig_result.get("destination_city")
            or orig_result.get("city")
            or "the destination"
        )

    # Trace back to root planning job to access session QA history
    root_job = db.get_root_job(payload.job_id)
    root_job_id = root_job["job_id"] if root_job else payload.job_id
    history_items = root_job.get("qa_history", []) if root_job else []

    if history_items:
        history_lines = []
        for idx, ex in enumerate(history_items, 1):
            q = ex.get("question") if isinstance(ex, dict) else getattr(ex, "question", "")
            a = ex.get("answer") if isinstance(ex, dict) else getattr(ex, "answer", "")
            history_lines.append(f"Turn {idx}:\nUser Question: {q}\nExpert Answer: {a}")
        conversation_history_str = "\n\n".join(history_lines)
    else:
        conversation_history_str = "No prior conversation history for this session."

    qa_inputs = {
        "destination_city": str(destination_city),
        "question": payload.question.strip(),
        "conversation_history": conversation_history_str,
        "language": payload.language,
    }

    new_job_id = str(uuid.uuid4())
    job_rec = db.create_job(
        job_id=new_job_id,
        job_type="qa",
        status="pending",
        parent_job_id=payload.job_id,
    )

    asyncio.create_task(_execute_qa_job(new_job_id, qa_inputs, root_job_id, payload.question.strip()))

    return JobStatusResponse(
        job_id=new_job_id,
        status="pending",
        created_at=job_rec["created_at"],
    )


@app.post("/api/smart-request", response_model=SmartRequestResponse)
@limiter.limit("30/minute")
async def smart_request_endpoint(request: Request, payload: SmartRequest):
    """
    Intelligent routing endpoint.
    Accepts a single user prompt string, classifies intent (new_trip, revision, question, comparison),
    and cleanly routes the request to existing handlers without duplicated logic.
    """
    from trip_planner.patterns.router import TripRouter, UserIntent

    has_active = bool(payload.job_id)
    classification = TripRouter.classify_intent(payload.text, has_active_job=has_active)
    intent = classification.intent
    extracted = classification.extracted_params

    # Route 1: NEW TRIP
    if intent == UserIntent.NEW_TRIP:
        dest_city = extracted.get("cities") or "Goa"
        origin_city = extracted.get("origin") or payload.origin or "Delhi"
        trip_len = extracted.get("trip_length", 3)
        budget_val = extracted.get("budget", 20000.0)

        plan_req = TripPlanRequest(
            origin=origin_city,
            cities=dest_city,
            trip_length=trip_len,
            budget=budget_val,
            interests=payload.text,
            travelers=1,
            language=payload.language,
            travel_mode="domestic",
            currency="INR",
        )
        plan_res = await plan_trip_endpoint(request, plan_req)
        return SmartRequestResponse(
            intent="new_trip",
            routed_to="/api/plan-trip",
            job_id=plan_res.job_id,
            status="pending",
            message=f"Routing to trip planner: {trip_len}-day trip to {dest_city} from {origin_city} (Budget: ₹{budget_val:,.0f}).",
            details={
                "cities": dest_city,
                "origin": origin_city,
                "trip_length": trip_len,
                "budget": budget_val,
            },
        )

    # Route 2: REVISION
    elif intent == UserIntent.REVISION:
        target_job_id = payload.job_id
        if not target_job_id:
            with db.get_connection() as conn:
                row = conn.cursor().execute(
                    "SELECT job_id FROM jobs WHERE status='complete' AND (job_type='plan' OR job_type='revise') ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                if row:
                    target_job_id = row["job_id"]

        if not target_job_id:
            raise HTTPException(
                status_code=400,
                detail="Revision intent detected, but no active or prior completed trip was found to revise. Please create a trip first.",
            )

        feedback_text = extracted.get("feedback") or payload.text
        rev_req = RevisionRequest(
            job_id=target_job_id,
            feedback=feedback_text,
            language=payload.language,
        )
        rev_res = await revise_trip_endpoint(request, rev_req)
        return SmartRequestResponse(
            intent="revision",
            routed_to="/api/revise-trip",
            job_id=rev_res.job_id,
            status="pending",
            message=f"Routing to itinerary reviser for trip {target_job_id[:8]} with feedback: '{feedback_text[:80]}...'",
            details={"parent_job_id": target_job_id, "feedback": feedback_text},
        )

    # Route 3: DESTINATION Q&A
    elif intent == UserIntent.QUESTION:
        target_job_id = payload.job_id
        if not target_job_id:
            with db.get_connection() as conn:
                row = conn.cursor().execute(
                    "SELECT job_id FROM jobs WHERE status='complete' ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                if row:
                    target_job_id = row["job_id"]

        if not target_job_id:
            temp_job_id = str(uuid.uuid4())
            db.create_job(job_id=temp_job_id, job_type="plan", status="complete", result={"destination_city": "India", "trip_length_days": 1})
            target_job_id = temp_job_id

        q_text = extracted.get("question") or payload.text
        q_req = DestinationQuestion(
            job_id=target_job_id,
            question=q_text,
            language=payload.language,
        )
        qa_res = await ask_question_endpoint(request, q_req)
        return SmartRequestResponse(
            intent="question",
            routed_to="/api/ask-question",
            job_id=qa_res.job_id,
            status="pending",
            message=f"Routing to local Q&A expert for question: '{q_text[:80]}...'",
            details={"job_id": qa_res.job_id, "question": q_text},
        )

    # Route 4: COMPARISON
    elif intent == UserIntent.COMPARISON:
        cities = extracted.get("cities") or []
        matching_job_ids = []
        if cities:
            with db.get_connection() as conn:
                for c in cities:
                    row = conn.cursor().execute(
                        "SELECT job_id FROM jobs WHERE status='complete' AND result LIKE ? ORDER BY created_at DESC LIMIT 1",
                        (f"%{c}%",),
                    ).fetchone()
                    if row:
                        matching_job_ids.append(row["job_id"])

        if len(matching_job_ids) >= 2:
            comp_res = await compare_trips_endpoint(CompareTripsRequest(job_ids=matching_job_ids[:3]))
            return SmartRequestResponse(
                intent="comparison",
                routed_to="/api/compare-trips",
                job_id=matching_job_ids[0],
                status="success",
                message=f"Comparing completed trips for: {', '.join(cities)}",
                details=comp_res,
            )
        else:
            return SmartRequestResponse(
                intent="comparison",
                routed_to="/api/compare-trips",
                job_id=None,
                status="info",
                message=f"Comparison intent detected between {', '.join(cities) if cities else 'destinations'}. "
                        f"Please generate itineraries for both to view side-by-side budget & weather comparison.",
                details={"cities": cities, "raw_query": payload.text},
            )

    raise HTTPException(status_code=400, detail="Unable to classify intent.")



@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Returns current status and results of a trip planning job from SQLite.
    """
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    res_data = job.get("result")
    if isinstance(res_data, dict) and res_data.get("cities_visited") and isinstance(res_data["cities_visited"], list) and len(res_data["cities_visited"]) > 1:
        reconcile_multi_city_itinerary(res_data)

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        result=res_data,
        error=job.get("error"),
        created_at=job.get("created_at"),
        travel_date=job.get("travel_date"),
        reminder_sent=job.get("reminder_sent"),
        checklist=db.get_checklist(job_id) if job.get("status") == "complete" else None,
    )


@app.get("/api/trip/{job_id}/checklist")
async def get_trip_checklist_endpoint(job_id: str):
    """Returns current checklist state for a trip job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Trip job '{job_id}' not found.")
    checklist = db.get_checklist(job_id)
    return {"job_id": job_id, "checklist": checklist}


@app.patch("/api/trip/{job_id}/checklist")
async def patch_trip_checklist_endpoint(job_id: str, payload: ChecklistItemPatch):
    """Updates a single checklist item state for a trip job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Trip job '{job_id}' not found.")
    updated = db.update_checklist_item(job_id, payload.item, payload.checked)
    return {"job_id": job_id, "checklist": updated}


@app.get("/api/trip/{job_id}/recommendations")
async def get_trip_recommendations_endpoint(job_id: str):
    """
    Looks at target job's destination_city & interests/country, queries other completed jobs
    with different destination_city, returns up to 3 recommendations with public fields only.
    Excludes user_email, qa_history, and private data.
    """
    target_job = db.get_job(job_id)
    if not target_job:
        raise HTTPException(status_code=404, detail=f"Trip job '{job_id}' not found.")

    target_res = target_job.get("result") or {}
    target_city = (target_res.get("destination_city") or "").strip().lower()
    target_country = (target_res.get("destination_country") or "India").strip().lower()

    raw_interests = str(target_res.get("interests") or "").lower()
    interest_words = set(re.findall(r"\w+", raw_interests)) - {"and", "the", "or", "in", "with", "for", "to", "a", "of"}

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT job_id, result FROM jobs
            WHERE status = 'complete' AND job_type = 'plan' AND job_id != ?;
            """,
            (job_id,),
        )
        rows = cursor.fetchall()

    candidates = []
    seen_cities = set()
    for row in rows:
        c_jid = row["job_id"]
        c_res = json.loads(row["result"]) if row["result"] else {}
        c_city = (c_res.get("destination_city") or "").strip()
        c_country = (c_res.get("destination_country") or "India").strip()

        if not c_city or c_city.lower() == target_city or c_city.lower() in seen_cities:
            continue

        c_text = (json.dumps(c_res)).lower()
        score = 0
        if c_country.lower() == target_country:
            score += 1

        for w in interest_words:
            if len(w) > 3 and w in c_text:
                score += 1

        if score > 0 or len(rows) <= 3:
            seen_cities.add(c_city.lower())
            days = c_res.get("days") or []
            theme_highlights = [d.get("theme") for d in days if isinstance(d, dict) and d.get("theme")]
            candidates.append({
                "score": score,
                "data": {
                    "job_id": c_jid,
                    "destination_city": c_city,
                    "destination_country": c_country,
                    "trip_length_days": c_res.get("trip_length_days", len(days)),
                    "total_estimated_cost": c_res.get("total_estimated_cost", 0.0),
                    "currency": c_res.get("currency", "INR"),
                    "theme_highlights": theme_highlights,
                }
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    recs = [c["data"] for c in candidates[:3]]

    return {"job_id": job_id, "recommendations": recs}


@app.post("/api/transcribe-audio")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribes uploaded audio file to text using Groq Whisper API."""
    allowed_types = {
        "audio/webm", "audio/mp3", "audio/mpeg", "audio/wav", "audio/x-wav",
        "audio/m4a", "audio/ogg", "audio/x-m4a", "audio/flac"
    }
    allowed_exts = {".webm", ".mp3", ".wav", ".m4a", ".ogg", ".flac"}

    file_ext = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()

    if file_ext not in allowed_exts and content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a valid audio file (webm, mp3, wav, m4a, ogg).",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty audio file uploaded.")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured.")

    try:
        import requests

        files = {
            "file": (file.filename or "audio.webm", contents, content_type or "audio/webm")
        }
        data = {
            "model": "whisper-large-v3",
            "response_format": "json",
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers=headers,
            files=files,
            data=data,
            timeout=60,
        )
        if resp.status_code != 200:
            logger.error("Groq Whisper API error %d: %s", resp.status_code, resp.text)
            raise HTTPException(status_code=500, detail=f"Audio transcription failed: {resp.text}")

        result = resp.json()
        transcript = result.get("text", "").strip()
        return {"transcript": transcript}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to transcribe audio: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription service error: {str(e)}")


@app.post("/api/inspire-from-photo")
async def inspire_from_photo(file: UploadFile = File(...)):
    """Analyzes an uploaded photo using Groq vision to suggest matching Indian destinations."""
    allowed_types = {
        "image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"
    }
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    file_ext = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()

    if file_ext not in allowed_exts and content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a valid image file (jpg, png, webp, gif).",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image file uploaded.")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured.")

    try:
        import base64

        import requests

        mime = content_type if content_type in allowed_types else "image/jpeg"
        img_b64 = base64.b64encode(contents).decode("utf-8")
        data_url = f"data:{mime};base64,{img_b64}"

        prompt = (
            "Analyze this photo carefully. Describe what scene/vibe is visually depicted in the photo. "
            "Suggest 2-3 Indian travel destinations (city/place names in India) that offer a similar vibe or landscape. "
            "IMPORTANT: Always suggest Indian destinations regardless of where the photo was taken (e.g. if the photo shows the Eiffel Tower, suggest Indian places with similar architectural or romantic vibes like Puducherry, Jaipur, or Udaipur, and explicitly note in your reasoning that you mapped the non-Indian scene to Indian equivalents per Phase 1 scope).\n\n"
            "Return valid JSON ONLY with exact keys:\n"
            "{\n"
            '  "detected_scene": "brief description of what is in the photo",\n'
            '  "suggested_destinations": ["City 1", "City 2"],\n'
            '  "reasoning": "explanation of why these Indian destinations match the photo"\n'
            "}"
        )

        payload = {
            "model": "qwen/qwen3.8-27b",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        if resp.status_code != 200:
            logger.error("Groq Vision API error %d: %s", resp.status_code, resp.text)
            raise HTTPException(status_code=500, detail=f"Image analysis failed: {resp.text}")

        raw_content = resp.json()["choices"][0]["message"]["content"].strip()
        cleaned_json = raw_content
        if "```" in cleaned_json:
            cleaned_json = re.sub(r"^```[a-zA-Z]*\n", "", cleaned_json)
            cleaned_json = re.sub(r"\n```$", "", cleaned_json).strip()

        data = json.loads(cleaned_json)
        return {
            "detected_scene": data.get("detected_scene", "Visual scene analyzed"),
            "suggested_destinations": data.get("suggested_destinations", []),
            "reasoning": data.get("reasoning", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to analyze image: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Vision service error: {str(e)}")


@app.get("/")
@app.get("/index.html")
async def serve_index():
    """Serves the frontend dashboard index.html."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "message": "AI Trip Planner API is running. Frontend index.html not found.",
        "docs_url": "/docs",
    }


def start():
    """CLI helper to run the web server."""
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("trip_planner.api.app:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    start()
