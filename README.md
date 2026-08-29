# 🇮🇳 AI Trip Planner — India Edition (v1)

[![CI](https://github.com/Phanikartheek/TRIP-PLANNER/actions/workflows/ci.yml/badge.svg)](https://github.com/Phanikartheek/TRIP-PLANNER/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-FF4F00.svg)](https://crewai.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://python.org)

A production-ready multi-agent trip-planning application built with [CrewAI](https://docs.crewai.com), [FastAPI](https://fastapi.tiangolo.com), and [Groq](https://groq.com), customized specifically for domestic Indian travel.

Three autonomous AI agents collaborate sequentially — evaluating candidate destinations across India, researching local attractions, cuisine, and transit routes, and generating a validated, structured `TripItinerary` complete with day-by-day morning/afternoon/evening schedules, budget breakdown in INR (₹), itemized expense tooltips, packing checklists, and multilingual output (English, Telugu, Hindi).

---

## ⚡ Quickstart (1-Click Run)

Start both the FastAPI backend and frontend dashboard together with automatic browser launch:

- **Windows (Double-click)**: Run **`run.bat`**
- **Cross-Platform / Terminal**:
  ```bash
  python run.py
  ```
- **PowerShell**:
  ```powershell
  .\run.ps1
  ```

Your default browser will automatically open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** with backend and frontend connected.

---

## 🌟 Key Features (Phase 1 — Built & Verified)

- **🇮🇳 India-Focused Travel Intelligence**: Tailored for domestic Indian getaways (e.g. Himachal hill stations, Kerala backwaters, Goa coastal routes, Rajasthan royal circuits, and spiritual hubs).
- **🗣️ Multilingual Output Support (Telugu & Hindi)**: Supports English (`en`), Telugu (`te` - తెలుగు), and Hindi (`hi` - हिंदी). Prompts instruct agents to generate itinerary narrative content in the requested language while maintaining strict Pydantic JSON structure and preserving native place names in English script for routing clarity.
- **🤖 3-Stage Sequential CrewAI Pipeline**:
  - `City Selection Expert`: Compares candidate cities against origin, duration, interests, seasonal weather, and budget to select the best destination.
  - `Local Tour Guide`: Curates attractions, regional cuisine/food recommendations, safety notes, and on-the-ground transit tips.
  - `Amazing Travel Concierge`: Assembles a structured day-by-day schedule with per-day cost estimates, total budget tracking, itemized expense breakdowns, and packing suggestions.
- **🔐 Magic-Link User Accounts & Saved Trips (`/api/auth/*`)**: Passwordless email authentication via secure magic links (`resend` API with local console fallback). Logged-in users have their generated trips automatically linked to their account and accessible on a dedicated **My Trips** dashboard (`/my-trips.html`).
- **🔗 Shareable Read-Only Trip Links (`/api/trip/{job_id}/share`)**: Generate public shareable read-only itinerary links (`/share.html?id={job_id}`) that strictly return public itinerary data while privacy-stripping user email addresses, account details, and internal QA history.
- **📄 ReportLab PDF Export (`/api/export-pdf`)**: One-click downloadable PDF itinerary export formatted with clean typography, destination summaries, daily schedules, itemized cost tables, and packing checklists.
- **💡 Itemized Cost Breakdown & Interactive Tooltips**: Detailed daily expense breakdowns (`cost_breakdown`) with hover/tap-to-toggle tooltips providing transparency into accommodation, food, transit, and sight entry fees.
- **📱 Touch-Friendly Mobile Responsiveness**: Optimized CSS layout with media queries (`768px`, `480px`, `390px`, `375px`), minimum $\ge 44\text{px}$ touch targets, vertical field stacking, and document-level touch tap listeners for seamless mobile operation.
- **💬 Conversational Replanning (`/api/revise-trip`)**: Refine generated itineraries with targeted follow-up feedback (e.g. "make day 3 more relaxing", "add vegetarian street food") processed by a dedicated concierge revision agent.
- **❓ Multi-Turn Destination Q&A with Grounding Badges (`/api/ask-question`)**: Ask follow-up travel questions about the selected destination with full multi-turn session history. Features coreference resolution, automated compound query decomposition, and self-reported grounding confidence indicators (`✓ Verified Place` vs `⚠ General Advice`).
- **📄 Pydantic Schema Validation & Cost Reconciliation**: Every pipeline task is validated against rigid Pydantic models (`backend/src/trip_planner/schemas/models.py`) with automatic post-validation reconciling `total_estimated_cost` with the exact sum of daily line-item expenses.
- **⚡ Fast Inference via Groq**: Uses Groq LLMs (`groq/qwen/qwen3.8-27b`) via CrewAI's `LLM` class for ultra low-latency planning with zero paid LLM subscription requirement.
- **🔍 Zero-Cost Search & Scraping Tools**: DuckDuckGo search integration with query caching and static HTML website scraping tools.
- **⏱️ SlowAPI Rate Limiting Protection**: IP-keyed request rate limiting protecting expensive LLM and authentication endpoints (`/api/auth/request-login` 3/hr, `/api/plan-trip` 5/hr, `/api/revise-trip` 10/hr, `/api/ask-question` 15/hr).
- **💾 Persistent SQLite Job Store**: Local database layer persisting trip jobs, user account sessions, revision lineage, and multi-turn QA history across server restarts with automatic startup crash reconciliation.

---

## 🔒 Security Notes

- **Magic Link Local Console Fallback Guard**: When `RESEND_API_KEY` is not set in `.env`, magic login links are printed directly to the server console accompanied by a loud **WARNING log**. This fallback is strictly designed for offline local development and **MUST NEVER** be enabled or used in deployed public environments.
- **Login Rate Limiting**: `POST /api/auth/request-login` is protected by IP-keyed rate limiting (`3 requests/hour`) to prevent magic link email harvesting, spam, and user harassment.
- **Timing Attack Resistance & Token Storage**: Authentication tokens (`login_token` and `session_token`) are 256-bit cryptographically secure random values generated via `secrets.token_urlsafe(32)`. Token validation is executed via direct SQLite Primary Key lookup (`SELECT ... WHERE token = ?`), providing $O(1)$ constant-time database index query execution and avoiding Python string comparison timing side-channels.
- **Privacy-Stripped Share Links**: The public share endpoint (`GET /api/trip/{job_id}/share`) returns strictly public `TripItinerary` data and completely omits `user_email`, `qa_history`, `status`, and database metadata.

---

## 🏛️ Architecture

```
[City Selection Expert]  ──>  [Local Tour Guide]  ──>  [Amazing Travel Concierge]
  (Evaluates weather,           (Researches sights,         (Constructs executable
   connectivity & costs)         regional food & transit)    itinerary & validates budget)
```

1. **Sequential Process**: Each task receives previous tasks' outputs as `context`.
2. **Schema Validation**: Task outputs conform to `CitySelection`, `CityGuide`, and `TripItinerary` contracts before moving to the next pipeline stage.

---

## 📁 Project Structure

```
trip_planner/
├── run.bat                          # 🚀 1-Click Windows Batch Launcher
├── run.ps1                          # 🚀 1-Click PowerShell Launcher
├── run.py                           # 🚀 1-Click Cross-Platform Launcher
├── frontend/                        # 🎨 Web Dashboard UI Assets
│   ├── index.html                   # Glassmorphic user interface & main form
│   ├── my-trips.html                # Saved trips dashboard for logged-in users
│   ├── share.html                   # Read-only public shareable itinerary page
│   ├── style.css                    # Design tokens & responsive styles (375px - 768px+)
│   └── app.js                       # Frontend client & state management
├── backend/                         # ⚙️ Python Backend Package & Agents
│   ├── src/
│   │   └── trip_planner/
│   │       ├── __init__.py
│   │       ├── crew.py              # Wires agents, tasks, tools, and LLM together
│   │       ├── main.py              # CLI entrypoint
│   │       ├── api/
│   │       │   ├── __init__.py
│   │       │   ├── app.py           # FastAPI server (/api/plan-trip, /api/auth/*, /api/export-pdf, /share)
│   │       │   └── db.py            # SQLite database layer (jobs, users, tokens, sessions)
│   │       ├── config/
│   │       │   ├── agents.yaml      # Agent roles, goals, and backstories
│   │       │   └── tasks.yaml       # Task descriptions, contexts, and expected outputs
│   │       ├── schemas/
│   │       │   ├── __init__.py
│   │       │   └── models.py        # Pydantic data contracts (Language, User, PDF, Share, CostBreakdown)
│   │       └── tools/
│   │           ├── __init__.py
│   │           ├── search_tools.py  # DuckDuckGo search BaseTool wrapper with caching
│   │           └── scrape_tools.py  # Web page scraping wrapper
│   └── tests/
│       ├── test_auth.py             # Magic-link, session lifecycle, and isolation tests
│       ├── test_cost_breakdown.py   # Expense itemization and budget reconciliation tests
│       ├── test_crew.py             # Crew wiring, task dependencies, schemas, and endpoint tests
│       ├── test_db.py               # SQLite database & crash recovery tests
│       ├── test_language.py         # Telugu and Hindi language validation tests
│       ├── test_pdf.py              # ReportLab PDF export endpoint tests
│       ├── test_share.py            # Public share link privacy & 404 endpoint tests
│       ├── test_tools.py            # Search tool unit tests (mocked network calls & caching)
│       └── run_live_verification.py # Playwright DOM box metrics & viewport inspection suite
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions CI workflow
├── .env.example                     # Environment configuration template
├── pyproject.toml                   # Project dependencies and tool configuration
└── README.md                        # Documentation
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Free Groq API Key from [console.groq.com/keys](https://console.groq.com/keys)
- Optional: Free Resend API Key from [resend.com](https://resend.com) for production magic-link email delivery

### 2. Installation

```bash
# Clone or navigate to the project directory
cd trip_planner

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows (PowerShell / CMD)
source .venv/bin/activate    # macOS / Linux

# Install dependencies in editable mode with dev packages
pip install -e ".[dev]"
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and set your API key:

```bash
cp .env.example .env
```

Inside `.env`:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
TRIP_PLANNER_MODEL=groq/qwen/qwen3.8-27b
RESEND_API_KEY=re_your_optional_resend_api_key_here
```

---

## 💻 Running the Application

### Option A: 1-Click Launcher (Recommended)
```bash
python run.py
# or double-click run.bat on Windows
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

### Option B: FastAPI Backend via Uvicorn
```bash
python -m uvicorn trip_planner.api.app:app --app-dir backend/src --host 127.0.0.1 --port 8000 --reload
```

---

## 🧪 Testing

Run the automated test suite to verify agent configurations, task wiring, search caching, schemas, multilingual validation, authentication, PDF generation, and public share endpoints:

```bash
$env:PYTHONPATH="backend/src"
pytest backend/tests/ -v
```

All 36 unit tests run deterministically against mock search inputs and Pydantic validation contracts without requiring live LLM calls.

---

## 🗺️ Roadmap (Phase 2 — Planned, Not Yet Built)

The following features are planned for future releases:

- [ ] **🌍 Global Destination Mode**: Expanding scope to support international travel destinations outside India.
- [ ] **💱 Dynamic Multi-Currency Engine**: Adding full real-time currency conversion APIs (`USD`, `EUR`, `GBP`).
- [ ] **🚆 Live Transport APIs**: Integrating real-time IRCTC train availability and domestic flight pricing APIs.
- [ ] **📅 Calendar (.ics) Export**: Exporting generated schedules directly to calendar files.
