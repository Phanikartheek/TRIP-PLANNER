# 🇮🇳 AI Trip Planner — Autonomous Multi-Agent Travel Engine (India Edition)

[![CI](https://github.com/Phanikartheek/TRIP-PLANNER/actions/workflows/ci.yml/badge.svg)](https://github.com/Phanikartheek/TRIP-PLANNER/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-FF4F00.svg)](https://crewai.com)
[![Leaflet](https://img.shields.io/badge/Leaflet-Interactive%20Maps-199900.svg?logo=leaflet&logoColor=white)](https://leafletjs.com)
[![Chart.js](https://img.shields.io/badge/Chart.js-Donut%20Analytics-FF6384.svg?logo=chartdotjs&logoColor=white)](https://www.chartjs.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://python.org)

An enterprise-grade, production-ready travel engine powered by autonomous AI agent patterns, [CrewAI](https://docs.crewai.com), and [FastAPI](https://fastapi.tiangolo.com). Specifically calibrated for domestic Indian travel and multi-city touring with real ground-transit realities (IRCTC rail, APSRTC/state express buses), zero-backtracking corridor sequencing, authentic visual media showcase, and interactive map routing with live Google Maps GPS navigation.

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

## 🤖 Four-Pattern Autonomous Agentic Architecture

The system implements the four foundational agentic workflows for robust, real-world execution:

```
                  ┌──────────────────────┐
                  │ 1. Routing Pattern   │
                  │ (Single vs Multi-City│
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

1. **Routing**: Analyzes user intent, destination topology, and travel style to route between single-destination deep itineraries and multi-city geographic corridor synthesis.
2. **Parallelization**: Concurrently fires independent research subagents to gather live weather forecasts, transport schedules, regional dining gems, and accommodation tiers.
3. **Orchestrator-Workers**: For multi-city journeys, decomposes the corridor into per-city bundles, dispatches concurrent workers via a `ThreadPoolExecutor`, and synthesizes sequential day-by-day plans.
4. **Evaluator-Optimizer**: Evaluates candidate itineraries against strict quality gates and budget ceilings (e.g. ₹25,000). When costs exceed the target budget, the system preserves raw, un-fabricated line-item estimates and attaches an honest, deterministic `budget_exceeded_warning` with exact overrun amount and percentage.

---

## 🌟 Core Real-World Features

### 📸 1. Authentic Visual Media Showcase & Tourism Insights
- **100% Authentic Imagery**: Curated high-resolution photos of South Indian temple gopurams, ancient Vijayanagara forts, sacred waterfalls, and authentic banana-leaf thalis (zero inaccurate stock photos).
- **"Why Famous & Why Visit" Guides**: Every visual highlight is accompanied by historical context, cultural significance, and budget advice (e.g. TTD electric buses, special entry tickets).

### 🗺️ 2. Interactive Map with Turn-by-Turn GPS Navigation
- **Pulsing Landmark Pins**: Interactive Leaflet map featuring custom category pins (`🏰`, `🛕`, `🌊`, `🏨`).
- **1-Click Route & Distance Tracing**: Click on any attraction card (e.g., *Chandragiri Fort & Raja Mahal*) to auto-scroll to the map, trace the dashed route path from the railway station/central hub, view road distance in km and transit duration, and launch live GPS driving navigation in Google Maps.

### 🚆 3. Zero-Backtracking Corridor Routing & Distance Optimizer
- **Smart Corridor Sequencing**: Uses nearest-neighbor geographic progression (e.g. Kurnool ➔ Tirupati ➔ Nellore ➔ Vijayawada ➔ Rajahmundry ➔ Kakinada ➔ Visakhapatnam) to prevent zig-zag travel.
- **Backtracking Reduction**: Computes and highlights total kilometers saved and travel hours preserved.

### 📊 4. Visual Budget Donut Analytics (Chart.js)
- **Interactive Donut Chart**: Breaks down total expenditure into 5 distinct expense buckets:
  1. 🏨 Stays & Accommodation
  2. 🍽️ Food & Regional Dining
  3. 🚆 Transit & Local Commute
  4. 🎟️ Activities & Sightseeing Entry Fees
  5. 🛡️ Contingency & Emergency Buffer
- **Honest Budget Transparency**: Real costs are preserved without artificial number fabrication. When the candidate itinerary exceeds the user's requested budget ceiling, the system flags it immediately with a prominent, honest warning detailing the exact overrun amount and percentage, along with actionable budget optimization suggestions.

### 💬 5. 1-Click WhatsApp Sharing & Offline PWA
- **WhatsApp Day Exporter**: Tap "Send Day X to WhatsApp" to generate a pre-formatted message with timings, hotel names, meals, and Google Maps directions ready to share with traveling companions.
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
├── frontend/                        # 🎨 Web Dashboard UI Assets
│   ├── index.html                   # Glassmorphic user interface & main form
│   ├── my-trips.html                # Saved trips dashboard for logged-in users
│   ├── share.html                   # Read-only public shareable itinerary page
│   ├── style.css                    # Design tokens & responsive styles (375px - 768px+)
│   ├── app.js                       # Frontend client, Leaflet maps & Chart.js logic
│   └── sw.js                        # Progressive Web App (PWA) service worker
├── backend/                         # ⚙️ Python Backend Package & Agents
│   ├── src/
│   │   └── trip_planner/
│   │       ├── crew.py              # CrewAI orchestrator & evaluator loops
│   │       ├── main.py              # CLI entrypoint
│   │       ├── api/
│   │       │   ├── app.py           # FastAPI server (/api/plan-trip, /api/auth/*, etc.)
│   │       │   └── db.py            # SQLite database layer (jobs, users, tokens)
│   │       ├── config/
│   │       │   ├── agents.yaml      # Agent roles, goals, and backstories
│   │       │   └── tasks.yaml       # Task descriptions and expected outputs
│   │       ├── patterns/            # Autonomous 4-Pattern Architecture
│   │       │   ├── router.py        # Pattern 1: Routing & Persona Classification
│   │       │   ├── parallelizer.py  # Pattern 2: Concurrent Multi-Source Researchers
│   │       │   ├── orchestrator.py  # Pattern 3: Orchestrator-Workers Multi-City Engine
│   │       │   └── evaluator_optimizer.py # Pattern 4: Evaluator-Optimizer Feedback Loop
│   │       ├── schemas/
│   │       │   └── models.py        # Pydantic data contracts (Language, User, PDF, Share)
│   │       └── tools/
│   │           ├── city_media.py    # Curated authentic visual registry & guides
│   │           ├── search_tools.py  # DuckDuckGo search wrapper with query caching
│   │           └── scrape_tools.py  # Web page scraping wrapper
│   └── tests/
│       ├── test_orchestrator_part_d.py       # Multi-city worker orchestration tests
│       ├── test_multicity_and_budget_alert.py # Budget ceiling & day enforcement tests
│       ├── test_auth.py                      # Magic-link & session tests
│       └── test_db.py                        # SQLite crash recovery tests
├── pyproject.toml                   # Project dependencies and tool configuration
└── README.md                        # Documentation
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Free Groq API Key from [console.groq.com/keys](https://console.groq.com/keys)
- Optional: Free Resend API Key from [resend.com](https://resend.com) for magic-link email delivery

### 2. Installation

```bash
# Clone or navigate to the project directory
cd trip_planner

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
TRIP_PLANNER_MODEL=groq/qwen/qwen3.8-27b
RESEND_API_KEY=re_your_optional_resend_api_key_here
```

---

## 💻 Running the Application

### 1-Click Launcher (Recommended)
```bash
python run.py
# or double-click run.bat on Windows
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## 🧪 Testing

Run the automated test suite to verify agent orchestration, day allocation, budget caps, and database operations:

```bash
pytest backend/tests/test_orchestrator_part_d.py backend/tests/test_multicity_and_budget_alert.py -v
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
