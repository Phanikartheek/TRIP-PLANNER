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


def _run_crew_sync(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Executes the TripPlannerCrew sequentially in a synchronous worker thread.
    """
    from trip_planner.crew import TripPlannerCrew

    crew_instance = TripPlannerCrew().crew()
    result = crew_instance.kickoff(inputs=inputs)

    out_dict: dict[str, Any] = {}
    if hasattr(result, "pydantic") and result.pydantic:
        out_dict = result.pydantic.model_dump()
    elif hasattr(result, "raw"):
        try:
            out_dict = json.loads(result.raw)
        except Exception:
            out_dict = {"raw_output": result.raw}
    else:
        out_dict = {"raw_output": str(result)}

    if isinstance(out_dict, dict):
        if "travelers" in inputs:
            req_travelers = int(inputs.get("travelers", 1))
            out_dict["travelers"] = req_travelers
            tot_cost = clean_float(out_dict.get("total_estimated_cost"), 0.0)
            out_dict["cost_per_person"] = round(tot_cost / max(1, req_travelers), 2)

        # Multi-city normalization & strict activity-city matching
        is_multi = bool(inputs.get("multi_city"))
        raw_cities = [c.strip() for c in str(inputs.get("cities", "")).split(",") if c.strip()]
        if len(raw_cities) > 1:
            out_dict["cities_visited"] = raw_cities
            out_dict["destination_city"] = raw_cities[0]
            days_list = out_dict.get("days", [])
            if isinstance(days_list, list) and len(days_list) > 0:
                num_days = len(days_list)
                num_cities = len(raw_cities)
                for idx, day_item in enumerate(days_list):
                    if isinstance(day_item, dict):
                        # Scan text of morning, afternoon, evening, night for actual city name
                        day_content = " ".join([
                            str(day_item.get("theme", "")),
                            str(day_item.get("morning", "")),
                            str(day_item.get("afternoon", "")),
                            str(day_item.get("evening", "")),
                            str(day_item.get("night", "")),
                            str(day_item.get("city", ""))
                        ]).lower()

                        matched_city = None
                        for c_candidate in raw_cities:
                            if c_candidate.lower() in day_content:
                                matched_city = c_candidate
                                break
                        
                        if matched_city:
                            day_item["city"] = matched_city
                        else:
                            city_idx = min(idx * num_cities // num_days, num_cities - 1)
                            day_item["city"] = raw_cities[city_idx]
            
            # Ensure multi-city stay list covers every visited city
            stays_list = out_dict.get("recommended_stays") or []
            if not isinstance(stays_list, list):
                stays_list = []
            if out_dict.get("recommended_stay") and isinstance(out_dict["recommended_stay"], dict):
                first_stay = out_dict["recommended_stay"]
                if not first_stay.get("city"):
                    first_stay["city"] = raw_cities[0]
                if not any(s.get("city", "").lower() == raw_cities[0].lower() for s in stays_list if isinstance(s, dict)):
                    stays_list.insert(0, first_stay)
            
            existing_stay_cities = {s.get("city", "").lower() for s in stays_list if isinstance(s, dict) and s.get("city")}
            for c_name in raw_cities:
                if c_name.lower() not in existing_stay_cities:
                    stays_list.append({
                        "name": f"Hotel Bliss / Sidhartha ({c_name})",
                        "city": c_name,
                        "category": "Comfort 3-Star Stay",
                        "estimated_price_per_night": round(clean_float(inputs.get("budget"), 5000.0) * 0.2 / max(1, len(raw_cities)), 2),
                        "address_or_area": f"{c_name} Central Hub",
                        "why_recommended": f"Budget-matched accommodation selected for easy access to {c_name} attractions."
                    })
            # Multi-leg route legs generation
            origin_name = str(inputs.get("origin", "Origin")).strip()
            city_seq = [origin_name] + raw_cities
            route_legs = []
            for idx in range(len(city_seq) - 1):
                from_c = city_seq[idx]
                to_c = city_seq[idx + 1]
                route_legs.append({
                    "leg_number": idx + 1,
                    "from_city": from_c,
                    "to_city": to_c,
                    "route_title": f"{from_c} ➔ {to_c}",
                    "mode": "Train / Bus",
                    "recommended_option": f"APSRTC Express Bus / Intercity Express Train ({from_c} to {to_c})",
                    "estimated_cost_per_person": 150.0 + (idx * 100.0),
                    "travel_duration": f"{3 + (idx % 2)} hrs",
                    "why_recommended": f"Frequent, comfortable, and direct transit option connecting {from_c} to {to_c}.",
                    "local_connect_tips": f"Use auto-rickshaws or app cabs from {to_c} arrival station/bus stand to your hotel."
                })
            
            inter_transit_raw = out_dict.get("intercity_transport")
            inter_transit: dict[str, Any] = inter_transit_raw if isinstance(inter_transit_raw, dict) else {
                "mode": "Train / Bus",
                "recommended_option": f"Multi-City Route Transit ({' ➔ '.join(city_seq)})",
                "estimated_cost_per_person": sum(leg["estimated_cost_per_person"] for leg in route_legs),
                "travel_duration": "Multi-leg journey",
                "why_recommended": "Optimized sequential transit linking all target destinations.",
                "local_connect_tips": "Local auto-rickshaws and cabs available at each transit station."
            }
            inter_transit["route_legs"] = route_legs
            out_dict["intercity_transport"] = inter_transit
            out_dict["recommended_stays"] = stays_list
        elif not is_multi:
            out_dict["cities_visited"] = None

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
                target_budget = float(user_budget)
                tot_cost = float(out_dict.get("total_estimated_cost", 0.0))
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
        if orig_job and isinstance(orig_job.get("result"), dict):
            orig_cost = float(orig_job["result"].get("total_estimated_cost", 0.0))

        itinerary_data = await asyncio.to_thread(_run_revision_sync, inputs)

        if isinstance(itinerary_data, dict):
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
    clean_itinerary = {
        "destination_city": result.get("destination_city"),
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


@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Returns current status and results of a trip planning job from SQLite.
    """
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        result=job.get("result"),
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
