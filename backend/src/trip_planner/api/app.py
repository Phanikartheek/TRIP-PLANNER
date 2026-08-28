"""
FastAPI application exposing the Trip Planner agent pipeline via REST API
and serving the frontend web dashboard.
"""

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from trip_planner.schemas.models import DestinationQuestion, QAResponse, RevisionRequest

load_dotenv()

app = FastAPI(
    title="AI Trip Planner API",
    description="Multi-agent trip planning engine with CrewAI and Groq",
    version="0.1.0",
)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# In-memory job store mapping job_id -> {status, result, error, created_at, inputs}
JOB_STORE: dict[str, dict[str, Any]] = {}


class TripPlanRequest(BaseModel):
    origin: str = Field(..., description="Origin city / transport hub")
    cities: str = Field(..., description="Comma-separated candidate cities to evaluate")
    interests: str = Field(..., description="User travel interests, hobbies, or vibes")
    trip_length: int = Field(default=5, ge=1, le=30, description="Duration of trip in days")
    budget: float = Field(default=25000.0, gt=0, description="Budget in chosen currency")
    currency: str = Field(default="INR", description="Budget currency code")
    travel_mode: str | None = Field(default="domestic", description="Travel mode (domestic vs international)")


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

    # Crew output with output_pydantic attaches the validated model
    if hasattr(result, "pydantic") and result.pydantic:
        return result.pydantic.model_dump()
    elif hasattr(result, "raw"):
        import json
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
        import json
        try:
            return json.loads(result.raw)
        except Exception:
            return {"raw_output": result.raw}
    return {"raw_output": str(result)}


async def _execute_trip_job(job_id: str, inputs: dict[str, Any]) -> None:
    """
    Background worker task running the CrewAI pipeline and storing results.
    """
    JOB_STORE[job_id]["status"] = "running"
    try:
        itinerary_data = await asyncio.to_thread(_run_crew_sync, inputs)
        JOB_STORE[job_id]["status"] = "complete"
        JOB_STORE[job_id]["result"] = itinerary_data
    except Exception as e:
        JOB_STORE[job_id]["status"] = "failed"
        JOB_STORE[job_id]["error"] = str(e)


async def _execute_revision_job(job_id: str, inputs: dict[str, Any]) -> None:
    """
    Background worker task running the single-agent revision task and storing results.
    """
    JOB_STORE[job_id]["status"] = "running"
    try:
        itinerary_data = await asyncio.to_thread(_run_revision_sync, inputs)
        JOB_STORE[job_id]["status"] = "complete"
        JOB_STORE[job_id]["result"] = itinerary_data
    except Exception as e:
        JOB_STORE[job_id]["status"] = "failed"
        JOB_STORE[job_id]["error"] = str(e)


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
    JOB_STORE[job_id]["status"] = "running"
    try:
        qa_data = await asyncio.to_thread(_run_qa_sync, inputs)
        qa_exchange = {
            "question": question,
            "answer": qa_data.get("answer", ""),
            "timestamp": time.time(),
            "grounded_claims": qa_data.get("grounded_claims", []),
            "ungrounded_claims": qa_data.get("ungrounded_claims", []),
        }

        if root_job_id in JOB_STORE:
            JOB_STORE[root_job_id].setdefault("qa_history", []).append(qa_exchange)
            qa_data["qa_history"] = list(JOB_STORE[root_job_id]["qa_history"])
        else:
            qa_data["qa_history"] = [qa_exchange]

        JOB_STORE[job_id]["status"] = "complete"
        JOB_STORE[job_id]["result"] = qa_data
    except Exception as e:
        JOB_STORE[job_id]["status"] = "failed"
        JOB_STORE[job_id]["error"] = str(e)


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
async def plan_trip_endpoint(request: TripPlanRequest):
    """
    Accepts trip parameters, initializes an async background job,
    and immediately returns a job_id for status polling.
    """
    raw_mode = (request.travel_mode or "").strip().lower()
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
        "origin": request.origin.strip(),
        "cities": request.cities.strip(),
        "interests": request.interests.strip(),
        "trip_length": str(request.trip_length),
        "budget": f"₹{request.budget:,.0f} {request.currency}" if request.currency == "INR" else f"{request.currency} {request.budget:,.0f}",
        "currency": request.currency,
    }

    job_id = str(uuid.uuid4())
    created_at = time.time()
    JOB_STORE[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": created_at,
        "inputs": crew_inputs,
    }

    # Kick off asynchronous background execution
    asyncio.create_task(_execute_trip_job(job_id, crew_inputs))

    return JobStatusResponse(
        job_id=job_id,
        status="pending",
        created_at=created_at,
    )


@app.post("/api/revise-trip", response_model=JobStatusResponse)
async def revise_trip_endpoint(request: RevisionRequest):
    """
    Accepts follow-up feedback on an existing completed itinerary,
    spawns a targeted single-agent revision task, and returns a new job_id.
    """
    if request.job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail="Original job not found")

    orig_job = JOB_STORE[request.job_id]
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
    import json
    itinerary_str = json.dumps(orig_itinerary, indent=2) if isinstance(orig_itinerary, dict) else str(orig_itinerary)

    revision_inputs = {
        "itinerary": itinerary_str,
        "feedback": request.feedback.strip(),
    }

    new_job_id = str(uuid.uuid4())
    created_at = time.time()
    JOB_STORE[new_job_id] = {
        "job_id": new_job_id,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": created_at,
        "inputs": revision_inputs,
        "parent_job_id": request.job_id,
    }

    asyncio.create_task(_execute_revision_job(new_job_id, revision_inputs))

    return JobStatusResponse(
        job_id=new_job_id,
        status="pending",
        created_at=created_at,
    )


@app.post("/api/ask-question", response_model=JobStatusResponse)
async def ask_question_endpoint(request: DestinationQuestion):
    """
    Accepts a direct question about a destination from an existing completed job,
    spawns a targeted single-agent Q&A task, and returns a job_id for status polling.
    """
    if request.job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail="Original job not found")

    orig_job = JOB_STORE[request.job_id]
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
            or orig_job.get("inputs", {}).get("cities", "the destination")
        )

    # Trace back to root planning job to access session QA history
    root_job_id = request.job_id
    curr = JOB_STORE[root_job_id]
    while curr.get("parent_job_id") and curr.get("parent_job_id") in JOB_STORE:
        root_job_id = curr["parent_job_id"]
        curr = JOB_STORE[root_job_id]

    history_items = JOB_STORE[root_job_id].get("qa_history", [])
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
        "question": request.question.strip(),
        "conversation_history": conversation_history_str,
    }

    new_job_id = str(uuid.uuid4())
    created_at = time.time()
    JOB_STORE[new_job_id] = {
        "job_id": new_job_id,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": created_at,
        "inputs": qa_inputs,
        "parent_job_id": request.job_id,
        "type": "destination_qa",
    }

    asyncio.create_task(_execute_qa_job(new_job_id, qa_inputs, root_job_id, request.question.strip()))

    return JobStatusResponse(
        job_id=new_job_id,
        status="pending",
        created_at=created_at,
    )


@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Returns current status and results of a trip planning job.
    """
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOB_STORE[job_id]
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
