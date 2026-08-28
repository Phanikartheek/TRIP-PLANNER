# 🇮🇳 AI Trip Planner — Multi-Agent Travel Engine

A multi-agent trip-planning application built with [CrewAI](https://docs.crewai.com), [FastAPI](https://fastapi.tiangolo.com), and [Groq](https://groq.com), featuring rich domestic Indian travel intelligence and global exploration.

Three autonomous AI agents collaborate sequentially — evaluating candidate destinations, researching local attractions, cuisine, and transit routes, and generating a validated, structured `TripItinerary` complete with day-by-day morning/afternoon/evening schedules, budget breakdown, and packing checklists.

---

## ⚡ Quickstart (1-Click Run)

Start both Frontend and Backend together with automatic browser opening:

- **Windows (Double-click)**: Run **`run.bat`**
- **Terminal (Cross-Platform)**:
  ```bash
  python run.py
  ```
- **PowerShell**:
  ```powershell
  .\run.ps1
  ```

Your browser will automatically open to **[http://127.0.0.1:8000](http://127.0.0.1:8000)** with the backend and frontend connected.

---

## 🌟 Key Features

- **🇮🇳 India-Focused & Global Travel Intelligence**: Tailored for domestic Indian getaways (hill stations, coastal routes, heritage circuits, spiritual hubs) and international travel.
- **🤖 3-Stage Sequential CrewAI Pipeline**:
  - `City Selection Expert`: Compares candidate cities against origin, duration, interests, seasonal weather, and budget to select the best destination.
  - `Local Tour Guide`: Curates attractions, regional cuisine/food recommendations, safety notes, and on-the-ground transit tips.
  - `Amazing Travel Concierge`: Assembles a structured day-by-day schedule with per-day cost estimates, total budget tracking, and packing suggestions.
- **💬 Conversational Replanning & Live Destination Q&A**: Refine itineraries dynamically with follow-up instructions (e.g. "make day 3 more relaxing", "add vegetarian street food") or ask instant questions about local transit and entry fees.
- **📄 Pydantic Schema Validation & Cost Reconciliation**: Every pipeline task is validated against rigid Pydantic models (`backend/src/trip_planner/schemas/models.py`) ensuring mathematical budget integrity.
- **⚡ Ultra-Fast Inference via Groq**: Uses Groq LLMs (`groq/qwen/qwen3.8-27b` / `groq/openai/gpt-oss-120b`) via LiteLLM for high-throughput, low-latency reasoning with zero required paid subscriptions.
- **🔍 Zero-Cost Search & Scraping Tools**: DuckDuckGo search integration and static HTML website scraping tools.
- **🌐 Glassmorphic UI Dashboard**: Responsive dark mode interface with destination presets, dietary preference pills, interactive budget slider, and live agent execution progress tracking.
- **📋 Export Options**: One-click Copy JSON, Download Markdown, and Print / PDF export.

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
│   │       │   └── app.py           # FastAPI server & REST API (/api/plan-trip, /api/health, /api/revise-trip)
│   │       ├── config/
│   │       │   ├── agents.yaml      # Agent roles, goals, and backstories
│   │       │   └── tasks.yaml       # Task descriptions, contexts, and expected outputs
│   │       ├── schemas/
│   │       │   ├── __init__.py
│   │       │   └── models.py        # Pydantic contracts (TripItinerary, CityGuide, CitySelection)
│   │       └── tools/
│   │           ├── __init__.py
│   │           ├── search_tools.py  # DuckDuckGo search BaseTool wrapper
│   │           └── scrape_tools.py  # Web page scraping wrapper
│   └── tests/
│       ├── test_crew.py             # Crew wiring, task dependencies, and schema tests
│       └── test_tools.py            # Search tool unit tests (mocked network calls)
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions CI workflow
├── .env.example                     # Environment configuration template
├── pyproject.toml                   # Project dependencies and tool configuration
└── README.md                        # Documentation
```

---

## 🚀 Setup & Manual Installation

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

# Install dependencies in editable mode
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

Run the automated test suite to verify agent configurations, task wiring, and schema validation:

```bash
$env:PYTHONPATH="backend/src"
pytest backend/tests/ -v
```

All unit tests run deterministically against mock search inputs and Pydantic validation contracts without invoking external LLM APIs.
