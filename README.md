<div align="center">

# 🇮🇳 AI Trip Planner
### Autonomous Multi-Agent Travel Engine — India & Global Edition

> **An enterprise-grade, agentic travel planning platform built with CrewAI, FastAPI, and Leaflet. Optimized for complex Indian domestic travel realities: zero-backtracking train & bus corridors, verified temple & monument logistics, honest budget ceiling gates, and automated multi-provider AI fallback resilience.**

<br/>

[![Live Demo](https://img.shields.io/badge/LIVE%20DEMO-Railway%20Cloud-00C7B7?style=for-the-badge&logo=railway&logoColor=white)](https://web-production-ca841.up.railway.app)
[![CI Status](https://img.shields.io/badge/CI%20BUILD-PASSING%20(100%25)-22c55e?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/Phanikartheek/TRIP-PLANNER/actions/workflows/ci.yml)
[![Benchmark Score](https://img.shields.io/badge/BENCHMARK-100%20%2F%20100-8b5cf6?style=for-the-badge&logo=speedtest&logoColor=white)](evals/benchmark_report.json)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![CrewAI](https://img.shields.io/badge/CrewAI-Agentic%20Flow-FF4F00?style=for-the-badge)](https://crewai.com)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)

<br/>

[🌐 Live Web App](https://web-production-ca841.up.railway.app) • [📊 System Architecture](#-system-architecture--flowcharts) • [🤖 4-Pattern Agent Workflows](#-the-4-pattern-agentic-engine) • [⚡ Quickstart](#-quickstart-1-click-launch) • [🧪 Test Suite & CI](#-testing-benchmarks--quality-gates) • [🚂 Railway Cloud Setup](#-railway-production-deployment)

</div>

---

## 📌 What is AI Trip Planner?

Most generic travel planning apps recommend disconnected tourist attractions, hallucinate non-existent travel routes, fail to account for transit schedules, and break when LLM rate limits are hit.

**AI Trip Planner** is an autonomous multi-agent engine purpose-engineered to solve complex ground realities:
- 🚆 **Real-World Transit Grounding**: Factors in Indian Railways (IRCTC), state express transport (APSRTC/TSRTC/KSRTC), ghat road electric bus schedules, and local auto-rickshaw norms.
- 🔄 **Zero-Backtracking Corridor Routing**: Uses nearest-neighbor geographic progression algorithms to prevent crisscross travel across state corridors (e.g. *Kurnool ➔ Tirupati ➔ Nellore ➔ Vijayawada ➔ Vizag*).
- 🛡️ **Self-Healing LLM Failover Pool**: Automatically catches API rate limits (`429`) and seamlessly transfers execution across a tiered fallback mesh without breaking user requests.
- 💰 **Honest Budget Ceiling Guardrails**: Enforces realistic budget limits without fabricating numbers; automatically detects budget overruns and issues transparent line-item warnings.
- 📱 **Mobile & PWA Ready**: Instant 1-tap WhatsApp day-by-day export, 1-tap SOS emergency contacts, regional phrasebooks, and offline itinerary caching.

---

## 🏗️ System Architecture & Flowcharts

### 1. End-to-End System Data Flow

```mermaid
flowchart TB
    subgraph ClientLayer["🖥️ Client & Access Layer"]
        UI["Modern Glassmorphism Web App<br/>(Vanilla JS / CSS / Leaflet / Chart.js)"]
        PWA["Offline PWA Worker<br/>(Cached Itineraries)"]
        WhatsApp["1-Tap WhatsApp Exporter<br/>(Day-by-Day Text)"]
    end

    subgraph APILayer["⚡ FastAPI Gateway & Security"]
        Router["Smart Intent Classifier<br/>(/api/smart-request)"]
        RateLimit["Per-Client Active Throttling &<br/>Daily Quota Guard (Retry-After: 86400)"]
        AuthMe["Magic-Link Auth & JWT Sessions<br/>(/api/auth/*)"]
    end

    subgraph AgenticCore["🤖 4-Pattern Agentic Execution Engine"]
        subgraph Pattern1["Pattern 1: Router"]
            Classifier{"Intent Classifier"}
            NewTrip["New Trip Intent"]
            ReviseTrip["Revision Intent"]
            QA["Destination Q&A"]
            Compare["Multi-Trip Compare"]
        end

        subgraph Pattern2["Pattern 2: Parallel Researchers"]
            WeatherAgent["🌦️ Weather Forecaster<br/>(Open-Meteo API)"]
            TransitAgent["🚆 Transit Corridors<br/>(Zero-Backtracking)"]
            DiningAgent["🍽️ Regional Food Gems<br/>(Authentic Eateries)"]
            StayAgent["🏨 Stay Recommendations<br/>(Station/Hub Proximity)"]
        end

        subgraph Pattern3["Pattern 3: Orchestrator-Workers"]
            Orchestrator["Corridor Orchestrator"]
            WorkerCityA["City Worker A"]
            WorkerCityB["City Worker B"]
            WorkerCityC["City Worker C"]
        end

        subgraph Pattern4["Pattern 4: Evaluator-Optimizer"]
            EvalLoop{"Budget & Quality<br/>Gate Evaluator"}
            CostCeiling["Enforce Budget Ceiling"]
            GroundedCheck["Audit Grounded Claims"]
        end
    end

    subgraph ResiliencyMesh["🛡️ Multi-Provider AI Fallback Pool"]
        Primary["1. Primary: Groq Qwen 3.8-27B"]
        Fallback1["2. Fallback: Groq LLaMA 3.1-8B"]
        Fallback2["3. Fallback: Groq LLaMA 3.3-70B"]
        OpenRouter["4. Provider Failover: OpenRouter LLaMA 3.3-70B"]
    end

    subgraph DataStorage["💾 Persistence & Observability"]
        SQLStore[("SQLAlchemy Store<br/>PostgreSQL / SQLite")]
        MetricsStore["Prometheus-Style Metrics<br/>(/api/metrics)"]
    end

    ClientLayer --> APILayer
    APILayer --> RateLimit
    RateLimit --> Router
    Router --> Classifier

    Classifier -->|New Trip| Pattern2
    Classifier -->|Multi-City Corridor| Pattern3
    Classifier -->|Question / Guide| QA

    Pattern2 --> Pattern4
    Pattern3 --> Pattern4

    Pattern4 -->|Rate Limit / 429| ResiliencyMesh
    Primary -.->|429 Trigger| Fallback1
    Fallback1 -.->|429 Trigger| Fallback2
    Fallback2 -.->|Groq Exhausted| OpenRouter

    Pattern4 --> SQLStore
    Pattern4 --> MetricsStore
    SQLStore --> UI
```

---

### 2. Autonomous AI Fallback Mesh (Zero-Downtime Pipeline)

When external model providers hit rate limits or API throttles, the system transparently cascades through fallback candidates:

```mermaid
stateDiagram-v2
    [*] --> Primary_Groq: Dispatch Request
    Primary_Groq --> Success: 200 OK
    Primary_Groq --> RateLimit1: HTTP 429 / Model Quota Exceeded

    state "Groq Qwen 3.8-27B" as Primary_Groq
    state "Groq LLaMA 3.1-8B" as Fallback1_Groq
    state "Groq LLaMA 3.3-70B" as Fallback2_Groq
    state "OpenRouter LLaMA 3.3-70B" as Secondary_OpenRouter

    RateLimit1 --> Fallback1_Groq: Auto-switch candidate #1
    Fallback1_Groq --> Success: 200 OK
    Fallback1_Groq --> RateLimit2: HTTP 429 / Quota Exceeded

    RateLimit2 --> Fallback2_Groq: Auto-switch candidate #2
    Fallback2_Groq --> Success: 200 OK
    Fallback2_Groq --> GroqExhausted: Groq Tier Exhausted

    GroqExhausted --> Secondary_OpenRouter: Cross-Provider Fallback to OpenRouter
    Secondary_OpenRouter --> Success: 200 OK
    Secondary_OpenRouter --> FinalError: Provider Outage

    Success --> LogMetrics: Record Fallback Metric
    LogMetrics --> [*]
```

---

## 🤖 The 4-Pattern Agentic Engine

The architecture mirrors enterprise agent workflows described in state-of-the-art LLM system research:

| Pattern | Component | Responsibility | Failure Handling |
| :--- | :--- | :--- | :--- |
| **1. Routing** | `patterns/router.py` | Analyzes incoming user queries and routes them into: new trip generation, day-by-day revisions, Q&A consultations, or multi-destination comparisons. | Falls back gracefully to standard full-itinerary planner. |
| **2. Parallelization** | `patterns/parallelizer.py` | Spawns parallel research threads via `ThreadPoolExecutor` to concurrently retrieve weather forecasts, transport routes, authentic dining, and accommodations. | Tools operate with independent try/catch fallbacks & local caching. |
| **3. Orchestrator-Workers** | `patterns/orchestrator.py` | Decomposes multi-city corridors into discrete city tasks. Each city worker executes independently; the orchestrator recombines results into a seamless timeline. | If a worker fails, neighboring days rebalance automatically. |
| **4. Evaluator-Optimizer** | `patterns/evaluator_optimizer.py` | Audits generated itineraries against user-defined budget ceilings (e.g. ₹20,000) and factual grounding schemas before finalizing output. | Transparently injects a `budget_exceeded_warning` with exact overrun math. |

---

## 🌟 Key Features

<table>
<tr>
<td width="50%">

### 🗺️ Turn-by-Turn Corridor Routing
- **Zero-Backtracking**: Calculates shortest topological paths between consecutive cities.
- **Interactive Leaflet Maps**: Displays pulsing category pins (`🏰`, `🛕`, `🌊`, `🏨`) and traces transit lines.
- **1-Click Google Maps GPS**: Directly launches live driving navigation from railway stations to attractions.

</td>
<td width="50%">

### 📊 Visual Budget Analytics (Chart.js)
- **5 Expense Buckets**:
  1. 🏨 Stays & Accommodation
  2. 🍽️ Food & Dining
  3. 🚆 Transit & Train/Bus
  4. 🎟️ Sightseeing Entry Fees
  5. 🛡️ Emergency Contingency Buffer
- **Honest Warning**: Exact breakdown of rupee overrun if budget is exceeded.

</td>
</tr>
<tr>
<td width="50%">

### 📸 Curated Authentic Media Registry
- **Zero Stock Photos**: High-resolution, verified imagery for South Indian temple gopurams, coastal ghats, and regional monuments.
- **"Why Famous & Why Visit"**: Entry fees, photography rules, dress codes, and best times to visit.

</td>
<td width="50%">

### 💬 1-Tap WhatsApp & Offline PWA
- **WhatsApp Day Exporter**: Exports daily schedules formatted for group travel chats.
- **Offline PWA**: Full itinerary accessible even inside train tunnels and remote mountain zones.

</td>
</tr>
<tr>
<td width="50%">

### 🚨 SOS Emergency & Regional Phrasebook
- **1-Tap Emergency Hotline (112)** with automatic nearby hospital and police navigation links.
- **Bilingual Phrasebook**: Telugu, Tamil, Kannada, Hindi, and English essential travel phrases.

</td>
<td width="50%">

### 🎙️ Multimodal Voice & Photo Inspiration
- **Voice Transcription**: Speak travel requests in natural language.
- **Vision Recognition**: Upload travel photos to identify monuments and automatically plan matching trips.

</td>
</tr>
</table>

---

## ⚡ Quickstart: 1-Click Launch

### Recommended (Windows)
Double-click **`run.bat`** in the project root. It will activate the environment, launch the FastAPI server, and open your browser automatically.

### Cross-Platform Terminal (macOS / Linux / Windows)
```bash
# Clone the repository
git clone https://github.com/Phanikartheek/TRIP-PLANNER.git
cd TRIP-PLANNER

# Create and activate virtual environment
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On macOS/Linux: source .venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"

# Launch the unified server
python run.py
```

Your browser will automatically open **`http://127.0.0.1:8000`**.

---

## ⚙️ Environment Configuration

Create a `.env` file in the project root (see [`.env.example`](.env.example)):

```env
# Primary AI Provider (Required)
GROQ_API_KEY=gsk_your_groq_api_key_here
TRIP_PLANNER_MODEL=groq/qwen/qwen3.8-27b

# Secondary AI Fallback Provider (Recommended for 99.9% uptime)
OPENROUTER_API_KEY=sk-or-v1-your_openrouter_api_key_here

# Database Configuration
DATABASE_URL=sqlite:///data/jobs.db
# For PostgreSQL in production:
# DATABASE_URL=postgresql://user:password@hostname:5432/dbname

# Rate Limiting & Proxy Configuration
DAILY_PLAN_LIMIT=50
TRUST_PROXY=true

# Optional: Passwordless Magic-Link Email Delivery (Resend)
RESEND_API_KEY=re_your_optional_resend_api_key_here
```

---

## 🧪 Testing, Benchmarks & Quality Gates

The codebase is protected by strict continuous integration (CI) quality gates covering code quality, integration testing, and agent reasoning benchmarks:

```bash
# 1. Lint and Import Order Validation (Ruff)
ruff check backend/

# 2. Run the Full Automated Test Suite (151 tests)
pytest backend/tests/ -k "not test_crew" -v

# 3. Execute the Autonomous Agent Benchmark Harness
python evals/harness.py
```

### Benchmark Summary
- **Test Suite**: **151 Passed**, 0 Failed, 17 Deselected
- **Agent Evaluation Harness**: **100.0 / 100.0 Score** (evaluates temporal logic, budget ceiling adherence, and multi-city geographic continuity)
- **CI Pipeline**: Automated via GitHub Actions on every commit to `main`

---

## 🚂 Railway Production Deployment

The project includes pre-configured deployment manifests ([`Dockerfile`](Dockerfile) and [`railway.json`](railway.json)):

1. Link your GitHub repository in the [Railway Dashboard](https://railway.app).
2. Configure your Environment Variables:
   - `GROQ_API_KEY`: Your Groq API key
   - `OPENROUTER_API_KEY`: Your OpenRouter API key *(optional, for fallback redundancy)*
   - `TRUST_PROXY`: `true`
   - `DAILY_PLAN_LIMIT`: `50`
3. Railway will build the container image and expose your service on a public HTTPS domain:
   - **Production URL**: `https://web-production-ca841.up.railway.app`
   - **Health Probe**: `GET /api/health`
   - **Observability Metrics**: `GET /api/metrics`

---

## 📡 Live API Endpoints Reference

| Method | Endpoint | Description |
| :---: | :--- | :--- |
| `GET` | `/` | Responsive web dashboard UI |
| `GET` | `/api/health` | Service uptime and Groq/OpenRouter connectivity health |
| `GET` | `/api/metrics` | Observability metrics (rate limits, latency, fallbacks, jobs) |
| `POST` | `/api/smart-request` | Dynamic intent classifier & request routing |
| `POST` | `/api/plan-trip` | Submits an asynchronous trip planning job |
| `GET` | `/api/status/{job_id}` | Polls job progress (5-stage tracking) and results |
| `POST` | `/api/ask-question` | Destination Q&A with grounded claims validation |
| `POST` | `/api/compare-trips` | Side-by-side comparative analysis of two destinations |
| `POST` | `/api/transcribe-audio` | Audio voice input transcription |
| `POST` | `/api/inspire-from-photo`| Multimodal photo analysis & destination matching |
| `GET` | `/api/trip/{job_id}/share` | Generates a clean, read-only shareable itinerary link |
| `GET` | `/api/trip/{job_id}/pdf` | Generates a downloadable PDF itinerary |
| `GET` | `/api/trip/{job_id}/calendar.ics` | Generates an iCalendar (.ics) file for mobile sync |

---

## 📄 License & Acknowledgments

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

- Powered by [CrewAI](https://crewai.com) for multi-agent workflows.
- High-speed LLM inference provided by [Groq](https://groq.com) and [OpenRouter](https://openrouter.ai).
- Maps & geospatial routing powered by [Leaflet.js](https://leafletjs.com) and OpenStreetMap.
- Real-time weather forecasting provided by [Open-Meteo](https://open-meteo.com).
