# 🇮🇳 AI Trip Planner — India Edition (v1)

A multi-agent trip-planning application built with [CrewAI](https://docs.crewai.com), [FastAPI](https://fastapi.tiangolo.com), and [Groq](https://groq.com), customized specifically for domestic Indian travel.

Three autonomous AI agents collaborate sequentially — evaluating candidate destinations across India, researching local attractions, cuisine, and transit routes, and generating a validated, structured `TripItinerary` complete with day-by-day morning/afternoon/evening schedules, budget breakdown in INR (₹), and packing checklists.

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
- **🤖 3-Stage Sequential CrewAI Pipeline**:
  - `City Selection Expert`: Compares candidate cities against origin, duration, interests, seasonal weather, and budget to select the best destination.
  - `Local Tour Guide`: Curates attractions, regional cuisine/food recommendations, safety notes, and on-the-ground transit tips.
  - `Amazing Travel Concierge`: Assembles a structured day-by-day schedule with per-day cost estimates, total budget tracking, and packing suggestions.
- **💬 Conversational Replanning (`/api/revise-trip`)**: Refine generated itineraries with targeted follow-up feedback (e.g. "make day 3 more relaxing", "add vegetarian street food") processed by a dedicated concierge revision agent.
- **❓ Live Destination Q&A (`/api/ask-question`)**: Ask follow-up travel questions about the selected destination (e.g. local transport tips, entrance fees, dress codes) with live web-search grounded answers.
- **📄 Pydantic Schema Validation & Cost Reconciliation**: Every pipeline task is validated against rigid Pydantic models (`backend/src/trip_planner/schemas/models.py`) with automatic post-validation reconciling `total_estimated_cost` with the sum of daily expenses.
- **⚡ Fast Inference via Groq**: Uses Groq LLMs (`groq/qwen/qwen3.8-27b`) via CrewAI's `LLM` class (LiteLLM-backed) for low-latency planning with zero paid LLM subscription requirement.
- **🔍 Zero-Cost Search & Scraping Tools**: DuckDuckGo search integration with query caching and static HTML website scraping tools.
- **🌐 Interactive Web Dashboard**: Responsive dark glassmorphic UI with domestic destination presets, dietary preference filters, budget slider, and live agent execution progress tracking.
- **🛡️ Phase 1 Allowlist Gate**: Backend validation on `/api/plan-trip` enforcing domestic Indian travel mode and rejecting unready international requests with clear Phase 2 messaging.
- **📋 Export Options**: One-click Copy JSON, Download Markdown, and Print / PDF export.

---

## 📐 Design Decisions

- **Groq via LiteLLM**: Chosen for ultra-low inference latency and generous free-tier token allowances, eliminating paid OpenAI subscription barriers while providing high-quality reasoning.
- **Config-Driven YAML Architecture**: Agent roles, backstories, and task prompts are isolated in `config/agents.yaml` and `config/tasks.yaml`. This cleanly decouples prompt tuning from Python orchestration logic.
- **Pydantic Schema Validation & Arithmetic Reconciliation**: Rather than trusting LLMs with arithmetic summation, Pydantic data contracts enforce structured JSON deliverables and derive `total_estimated_cost` as the exact sum of daily line-item expenses.
- **Strict Phase 1 Domestic Scope & API-Level Allowlist Gate**: Focused domain specialization delivers deep regional expertise (monsoon seasonality, train/flight routing, local cuisine) before international scaling. A strict API allowlist prevents bypass regardless of client-side state.

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
│   ├── index.html                   # Glassmorphic user interface
│   ├── style.css                    # Design tokens & responsive styles
│   └── app.js                       # Frontend client & state management
├── backend/                         # ⚙️ Python Backend Package & Agents
│   ├── src/
│   │   └── trip_planner/
│   │       ├── __init__.py
│   │       ├── crew.py              # Wires agents, tasks, tools, and LLM together
│   │       ├── main.py              # CLI entrypoint
│   │       ├── api/
│   │       │   ├── __init__.py
│   │       │   └── app.py           # FastAPI server (/api/plan-trip, /api/revise-trip, /api/ask-question)
│   │       ├── config/
│   │       │   ├── agents.yaml      # Agent roles, goals, and backstories
│   │       │   └── tasks.yaml       # Task descriptions, contexts, and expected outputs
│   │       ├── schemas/
│   │       │   ├── __init__.py
│   │       │   └── models.py        # Pydantic data contracts
│   │       └── tools/
│   │           ├── __init__.py
│   │           ├── search_tools.py  # DuckDuckGo search BaseTool wrapper with caching
│   │           └── scrape_tools.py  # Web page scraping wrapper
│   └── tests/
│       ├── test_crew.py             # Crew wiring, task dependencies, schemas, and endpoint tests
│       └── test_tools.py            # Search tool unit tests (mocked network calls & caching)
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

### Option C: Terminal CLI Mode
```bash
$env:PYTHONPATH="backend/src"
python -m trip_planner.main
```

---

## 🧪 Testing

Run the automated test suite to verify agent configurations, task wiring, search caching, schemas, and API endpoints:

```bash
$env:PYTHONPATH="backend/src"
pytest backend/tests/ -v
```

All 18 unit tests run deterministically against mock search inputs and Pydantic validation contracts without invoking external LLM APIs.

---

## 🗺️ Roadmap (Phase 2 — Planned, Not Yet Built)

The following features are planned for future releases:

- [ ] **🌍 Global Destination Mode**: Expanding scope to support international travel destinations outside India (the Global toggle in the web UI is currently in disabled preview state, and the backend actively validates domestic-only requests for Phase 1).
- [ ] **💱 Dynamic Multi-Currency Engine**: Adding full multi-currency conversion (`USD`, `EUR`, `GBP`) with real-time conversion rates.
- [ ] **🚆 Live Transport APIs**: Integrating real-time IRCTC train availability and domestic flight pricing APIs.
- [ ] **📅 Calendar (.ics) Export**: Exporting generated schedules directly to calendar files.
