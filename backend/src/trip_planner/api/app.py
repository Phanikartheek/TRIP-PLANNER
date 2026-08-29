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
from io import BytesIO
from pathlib import Path
from typing import Any

import resend
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
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
)

load_dotenv()
logger = logging.getLogger("trip_planner.api")

# Initialize Rate Limiter keyed by remote IP
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AI Trip Planner API",
    description="Multi-agent trip planning engine with CrewAI and Groq",
    version="0.1.0",
)
app.state.limiter = limiter
def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    from fastapi.responses import JSONResponse

    response = JSONResponse(
        {"error": f"Rate limit exceeded: {exc.detail}"},
        status_code=429,
    )
    response.headers["Retry-After"] = "3600"
    return response


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initializes the SQLite job store and reconciles interrupted jobs."""
    db.init_db()


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


class JobStatusResponse(BaseModel):
    job_id: str
    status: str = Field(description="Job status: pending, running, complete, or failed")
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float | None = None


def _run_crew_sync(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Executes the TripPlannerCrew sequentially in a synchronous worker thread.
    """
    from trip_planner.crew import TripPlannerCrew

    crew_instance = TripPlannerCrew().crew()
    result = crew_instance.kickoff(inputs=inputs)

    if hasattr(result, "pydantic") and result.pydantic:
        return result.pydantic.model_dump()
    elif hasattr(result, "raw"):
        try:
            return json.loads(result.raw)
        except Exception:
            return {"raw_output": result.raw}
    return {"raw_output": str(result)}


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
    """
    db.update_job(job_id, status="running")
    try:
        itinerary_data = await asyncio.to_thread(_run_crew_sync, inputs)
        db.update_job(job_id, status="complete", result=itinerary_data)
    except Exception as e:
        db.update_job(job_id, status="failed", error=str(e))


async def _execute_revision_job(job_id: str, inputs: dict[str, Any]) -> None:
    """
    Background worker task running the single-agent revision task and storing results.
    """
    db.update_job(job_id, status="running")
    try:
        itinerary_data = await asyncio.to_thread(_run_revision_sync, inputs)
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
    }
    return clean_itinerary



@app.post("/api/auth/request-login")
@limiter.limit("3/hour")
async def request_login_endpoint(request: Request, payload: LoginRequest):
    raw_email = payload.email.strip().lower()
    if "@" not in raw_email or "." not in raw_email:
        raise HTTPException(status_code=400, detail="Invalid email address format.")

    token = db.create_login_token(raw_email)
    verify_url = f"{request.base_url}api/auth/verify?token={token}"

    resend_key = os.getenv("RESEND_API_KEY")
    if resend_key:
        resend.api_key = resend_key
        try:
            resend.Emails.send({
                "from": "AI Trip Planner <onboarding@resend.dev>",
                "to": [raw_email],
                "subject": "Magic Link Sign In for AI Trip Planner",
                "html": f'<p>Click the link below to sign in to AI Trip Planner:</p><p><a href="{verify_url}">Sign In to AI Trip Planner</a></p><p>This link expires in 15 minutes.</p>',
            })
        except Exception as e:
            logger.error(f"Failed to dispatch magic link email via Resend API: {e}")
    else:
        logger.warning(
            "\n" + "=" * 80 +
            "\n[SECURITY WARNING] RESEND_API_KEY is NOT configured in environment!\n" +
            "Magic login link printed to server console FOR LOCAL DEVELOPMENT ONLY.\n" +
            "DO NOT USE THIS FALLBACK IN A DEPLOYED OR PUBLIC ENVIRONMENT!\n" +
            f"MAGIC LOGIN LINK FOR {raw_email}: {verify_url}\n" +
            "=" * 80 + "\n"
        )
        print(f"\n[MAGIC LINK FOR {raw_email}]: {verify_url}\n", flush=True)

    return {
        "message": "If this email is valid, a magic login link has been sent. Please check your inbox or server logs."
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


@app.post("/api/plan-trip", response_model=JobStatusResponse)
@limiter.limit("5/hour")
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

    crew_inputs = {
        "origin": payload.origin.strip(),
        "cities": payload.cities.strip(),
        "interests": payload.interests.strip(),
        "trip_length": str(payload.trip_length),
        "budget": f"₹{payload.budget:,.0f} {payload.currency}" if payload.currency == "INR" else f"{payload.currency} {payload.budget:,.0f}",
        "currency": payload.currency,
        "language": payload.language,
    }

    user_email = _get_current_user_email(request)
    job_id = str(uuid.uuid4())
    job_rec = db.create_job(job_id=job_id, job_type="plan", status="pending", user_email=user_email)

    # Kick off asynchronous background execution
    asyncio.create_task(_execute_trip_job(job_id, crew_inputs))

    return JobStatusResponse(
        job_id=job_id,
        status="pending",
        created_at=job_rec["created_at"],
    )


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
    )


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
