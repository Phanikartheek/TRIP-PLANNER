# 🇮🇳 AI Trip Planner — Autonomous Multi-Agent Travel Engine (India Edition)

[![CI](https://github.com/Phanikartheek/TRIP-PLANNER/actions/workflows/ci.yml/badge.svg)](https://github.com/Phanikartheek/TRIP-PLANNER/actions/workflows/ci.yml)
[![Live on Railway](https://img.shields.io/badge/Railway-Live%20Demo-0B0D0E?logo=railway&logoColor=white)](https://web-production-ca841.up.railway.app)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-FF4F00.svg)](https://crewai.com)
[![Leaflet](https://img.shields.io/badge/Leaflet-Interactive%20Maps-199900.svg?logo=leaflet&logoColor=white)](https://leafletjs.com)
[![Chart.js](https://img.shields.io/badge/Chart.js-Donut%20Analytics-FF6384.svg?logo=chartdotjs&logoColor=white)](https://www.chartjs.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://python.org)

An enterprise-grade, production-ready travel engine powered by autonomous AI agent patterns, [CrewAI](https://docs.crewai.com), and [FastAPI](https://fastapi.tiangolo.com). Specifically calibrated for domestic Indian travel and multi-city touring with real ground-transit realities (IRCTC rail, APSRTC/state express buses), zero-backtracking corridor sequencing, authentic visual media showcase, interactive map routing with live Google Maps GPS navigation, and automated multi-provider LLM fallback resilience.

---

## 🌐 Live Production Demo
- **URL**: **[https://web-production-ca841.up.railway.app](https://web-production-ca841.up.railway.app)**
- **API Health**: `https://web-production-ca841.up.railway.app/api/health`
- **Observability Metrics**: `https://web-production-ca841.up.railway.app/api/metrics`
- **Interactive OpenAPI Docs**: `https://web-production-ca841.up.railway.app/docs`

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

## 🛡️ Multi-Provider AI Fallback & Reliability Engine

To ensure 99.9% uptime and zero disruptions during LLM rate limits (429) or token exhaustion:

```
[User Request]
       │
       ▼
1. Primary: Groq Qwen 3.8-27B (groq/qwen/qwen3.8-27b)
       │ (On 429 Rate Limit / Error)
       ▼
2. Fallback 1: Groq LLaMA 3.1-8B (groq/llama-3.1-8b-instant)
       │ (On 429 Rate Limit / Error)
       ▼
3. Fallback 2: Groq LLaMA 3.3-70B (groq/llama-3.3-70b-versatile)
       │ (On Groq Quota Exhaustion)
       ▼
4. Secondary Provider: OpenRouter LLaMA 3.3-70B (openrouter/meta-llama/llama-3.3-70b-instruct)
```

- **Transparent Logging**: Every provider transition is logged with model names and exact reasons.
- **Observability Metrics (`/api/metrics`)**: Exposes real-time provider fallbacks, error rates, average latency, and active generation counts.

---

## 🤖 Four-Pattern Autonomous Agentic Architecture

The system implements the four foundational agentic workflows for robust, real-world execution:

```
                  ┌──────────────────────┐
                  │ 1. Routing Pattern   │
                  │ (Intent: Trip / Q&A /│
                  │  Comparison / Edit)  │
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│ 2. Parallel Researchers │       │ 3. Orchestrator-Workers │
│ (Weather, Transit, Food,│       │ (Deconstructs Multi-City│
│  Accommodations, Sights)│       │  into Parallel Bundles) │
└───────────┬─────────────┘       └───────────┬─────────────┘
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ 4. Evaluator-        │
                  │    Optimizer Loop    │
                  │ (Budget Ceiling Gate,│
                  │  Quality Validation) │
                  └──────────────────────┘
```

1. **Routing Pattern (`/api/smart-request`)**: Classifies user queries between new trip planning, trip revision, multi-city comparison, and destination Q&A.
2. **Parallelization**: Concurrently fires independent research subagents to gather live weather forecasts, transport schedules, regional dining gems, and accommodation tiers.
3. **Orchestrator-Workers**: For multi-city journeys, decomposes the corridor into per-city bundles, dispatches concurrent workers via a `ThreadPoolExecutor`, and synthesizes sequential day-by-day plans.
4. **Evaluator-Optimizer**: Evaluates candidate itineraries against strict quality gates and budget ceilings (e.g. ₹25,000). When costs exceed the target budget, the system preserves raw line-item estimates and attaches a deterministic `budget_exceeded_warning` with exact overrun amount and percentage.

---

## 🌟 Core Real-World Features

### 📸 1. Authentic Visual Media Showcase & Tourism Insights
- **100% Authentic Imagery**: Curated high-resolution photos of South Indian temple gopurams, ancient Vijayanagara forts, sacred waterfalls, and authentic banana-leaf thalis.
- **"Why Famous & Why Visit" Guides**: Historical context, cultural significance, and budget advice (e.g. TTD electric buses, special entry tickets).

### 🗺️ 2. Interactive Map with Turn-by-Turn GPS Navigation
- **Pulsing Landmark Pins**: Interactive Leaflet map featuring custom category pins (`🏰`, `🛕`, `🌊`, `🏨`).
- **1-Click Route & Distance Tracing**: Click on any attraction card (e.g., *Chandragiri Fort & Raja Mahal*) to auto-scroll to the map, trace the dashed route path from the railway station/central hub, view road distance in km, and launch live GPS driving navigation in Google Maps.

### 🚆 3. Zero-Backtracking Corridor Routing & Distance Optimizer
- **Smart Corridor Sequencing**: Uses nearest-neighbor geographic progression (e.g. Kurnool ➔ Tirupati ➔ Nellore ➔ Vijayawada ➔ Rajahmundry ➔ Kakinada ➔ Visakhapatnam) to eliminate zig-zag travel and save transit hours.

### 📊 4. Visual Budget Donut Analytics (Chart.js)
- **Interactive Donut Chart**: Breaks down expenditure into 5 distinct expense buckets:
  1. 🏨 Stays & Accommodation
  2. 🍽️ Food & Regional Dining
  3. 🚆 Transit & Local Commute
  4. 🎟️ Activities & Sightseeing Entry Fees
  5. 🛡️ Contingency & Emergency Buffer
- **Honest Budget Transparency**: Real costs are preserved without artificial number fabrication, accompanied by actionable budget tips.

### 💬 5. 1-Click WhatsApp Sharing & Offline PWA
- **WhatsApp Day Exporter**: Tap "Send Day X to WhatsApp" to generate a pre-formatted message with timings, hotel names, meals, and Google Maps directions.
- **PWA Ready**: Offline-capable service worker for uninterrupted access in low-connectivity areas.

### 🔐 6. Magic-Link Auth & Multi-Turn Q&A
- **Passwordless Authentication**: Secure magic links for saving and revisiting past trips on the *My Trips* dashboard.
- **Context-Aware Travel Q&A (`/api/ask-question`)**: Inquire about local dress codes, festival timings, and transport tips with grounded response badges (`✓ Verified Place`).

---

## 📁 Project Structure

```
trip_planner/
├── run.bat                          # 🚀 1-Click Windows Batch Launcher
├── run.ps1                          # 🚀 1-Click PowerShell Launcher
├── run.py                           # 🚀 1-Click Cross-Platform Server Launcher
├── Dockerfile                       # 🐳 Production container definition (Railway / Render)
├── railway.json                     # ⚙️ Railway deployment configuration
├── evals/                           # 📈 Agent evaluation & benchmark harness
│   ├── harness.py                   # Automated benchmark runner (100/100 score)
│   └── benchmark_report.json        # Benchmark execution report
├── frontend/                        # 🎨 Web Dashboard UI Assets
│   ├── index.html                   # Glassmorphic user interface & main form
│   ├── my-trips.html                # Saved trips dashboard for logged-in users
│   ├── share.html                   # Read-only public shareable itinerary page
│   ├── style.css                    # Design tokens & responsive styles
│   ├── app.js                       # Frontend client, Leaflet maps & Chart.js logic
│   ├── manifest.json                # PWA web app manifest
│   └── sw.js                        # Progressive Web App (PWA) service worker
├── backend/                         # ⚙️ Python Backend Package & Agents
│   ├── src/
│   │   └── trip_planner/
│   │       ├── crew.py              # CrewAI orchestrator, LLM fallback pool
│   │       ├── main.py              # CLI entrypoint
│   │       ├── api/
│   │       │   ├── app.py           # FastAPI server & route handlers
│   │       │   ├── db.py            # SQLAlchemy database layer (SQLite / PostgreSQL)
│   │       │   ├── metrics.py       # Production observability metrics
│   │       │   └── repository.py    # Job persistence repository
│   │       ├── config/
│   │       │   ├── agents.yaml      # Agent roles, goals, and backstories
│   │       │   └── tasks.yaml       # Task descriptions and expected outputs
│   │       ├── patterns/            # Autonomous 4-Pattern Architecture
│   │       │   ├── router.py        # Pattern 1: Routing & Intent Classification
│   │       │   ├── parallelizer.py  # Pattern 2: Concurrent Multi-Source Researchers
│   │       │   ├── orchestrator.py  # Pattern 3: Orchestrator-Workers Multi-City Engine
│   │       │   └── evaluator_optimizer.py # Pattern 4: Evaluator-Optimizer Feedback Loop
│   │       ├── schemas/
│   │       │   └── models.py        # Pydantic data contracts
│   │       └── tools/
│   │           ├── city_media.py    # Curated authentic visual registry & guides
│   │           ├── weather_tools.py # Open-Meteo live weather forecast integration
│   │           └── search_tools.py  # Search wrapper with query caching
│   └── tests/                       # 151+ Automated Tests (Pytest)
├── pyproject.toml                   # Project dependencies and tool configuration
└── README.md                        # Project documentation
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Free Groq API Key from [console.groq.com/keys](https://console.groq.com/keys)
- Optional: OpenRouter API Key from [openrouter.ai/keys](https://openrouter.ai/keys) for fallback redundancy
- Optional: Free Resend API Key from [resend.com](https://resend.com) for magic-link email delivery

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/Phanikartheek/TRIP-PLANNER.git
cd TRIP-PLANNER

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows (PowerShell / CMD)
source .venv/bin/activate    # macOS / Linux

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and configure your keys:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
OPENROUTER_API_KEY=sk-or-v1-your_openrouter_api_key_here  # Optional fallback
TRIP_PLANNER_MODEL=groq/qwen/qwen3.8-27b
DAILY_PLAN_LIMIT=50
DATABASE_URL=sqlite:///data/jobs.db                        # Or postgresql://user:pass@host/db
RESEND_API_KEY=re_your_optional_resend_api_key_here
```

---

## 🧪 Testing & CI Quality Gates

Run the test suite and evaluation harness locally:

```bash
# 1. Lint with Ruff
ruff check backend/

# 2. Run the 151-test suite
pytest backend/tests/ -k "not test_crew" -v

# 3. Run the Agent Evaluation & Benchmark Harness
python evals/harness.py
```

---

## 🚂 Deployment to Railway

The application includes native Railway deployment configuration with zero setup needed:

1. Connect your GitHub repository (`Phanikartheek/TRIP-PLANNER`) on [railway.com](https://railway.com).
2. Set Environment Variables in Railway dashboard:
   - `GROQ_API_KEY` (Required)
   - `OPENROUTER_API_KEY` (Optional, recommended for fallback resilience)
   - `TRUST_PROXY=true`
   - `DAILY_PLAN_LIMIT=50`
3. Railway auto-detects `Dockerfile` or `pyproject.toml`, builds the container, and assigns your public domain (e.g. `https://web-production-ca841.up.railway.app`).

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
