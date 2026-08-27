# 🇮🇳 AI Trip Planner — India Edition (v1)

A multi-agent trip-planning pipeline built with [CrewAI](https://docs.crewai.com) and [Groq](https://groq.com), customized specifically for domestic Indian travel.

Three autonomous AI agents collaborate sequentially — evaluating candidate Indian destinations, researching local sights, cuisine, and transit, and generating a validated, structured `TripItinerary` with day-by-day morning/afternoon/evening schedules, budget tracking in INR (₹), and packing checklists.

---

## 🌟 Key Features (Phase 1 — Built & Verified)

- **🇮🇳 India-Focused Travel Intelligence**: Tailored for domestic Indian itineraries (e.g. hill stations, beach getaways, royal heritage routes, and spiritual hubs).
- **🤖 3-Stage Sequential CrewAI Pipeline**:
  - `City Selection Expert`: Compares candidate cities against origin, duration, interests, seasonal weather, and budget to select the best destination.
  - `Local Tour Guide`: Curates attractions, regional cuisine/food recommendations, safety notes, and on-the-ground transit tips.
  - `Amazing Travel Concierge`: Assembles a structured day-by-day schedule with per-day cost estimates, total budget tracking, and packing suggestions.
- **📄 Pydantic Schema Validation**: Every pipeline task is validated against rigid Pydantic models (`src/trip_planner/schemas/models.py`), ensuring predictable, machine-readable JSON deliverables rather than unstructured free text.
- **⚡ Fast Inference via Groq**: Uses Groq LLMs via CrewAI's `LLM` class (LiteLLM-backed) for low-latency planning with zero paid LLM subscription requirement.
- **🔍 Zero-Cost Search & Scraping Tools**: DuckDuckGo search integration and static HTML website scraping tools.
- **🌐 Interactive Web Dashboard & REST API**: Full FastAPI server with a dark glassmorphic responsive UI, destination presets, dietary filter pills, and live agent execution progress tracking.
- **💻 CLI Entrypoint**: Interactive terminal interface prompting for origin, candidate cities, interests, trip duration, and budget.
- **🛡️ Built-in Rate Limit Resilience**: Automatic exponential retry backoff wrapper around Groq API calls.

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
├── src/
│   └── trip_planner/
│       ├── __init__.py
│       ├── crew.py                  # Wires agents, tasks, tools, and LLM together
│       ├── main.py                  # CLI entrypoint
│       ├── config/
│       │   ├── agents.yaml          # Agent roles, goals, and backstories
│       │   └── tasks.yaml           # Task descriptions, contexts, and expected outputs
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── models.py            # Pydantic data contracts (TripItinerary, CityGuide, CitySelection)
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── search_tools.py      # DuckDuckGo search BaseTool wrapper
│       │   └── scrape_tools.py      # Web page scraping wrapper
│       └── web/
│           ├── __init__.py
│           ├── app.py               # FastAPI server and REST endpoints (/api/plan-trip, /api/health)
│           └── static/
│               ├── index.html       # Web UI dashboard
│               ├── style.css        # Dark glassmorphic responsive styling
│               └── app.js           # Frontend controller & reactive state
├── tests/
│   ├── test_crew.py                 # Crew wiring, task dependencies, and schema tests
│   └── test_tools.py                # Search tool unit tests (mocked network calls)
├── .env.example                     # Environment configuration template
├── pyproject.toml                   # Project dependencies and packaging configuration
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

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and configure your API key:

```bash
cp .env.example .env
```

Inside `.env`:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
TRIP_PLANNER_MODEL=groq/openai/gpt-oss-120b
```

---

## 💻 Running the Application

### Option A: Interactive Web Dashboard (Recommended)

```bash
$env:PYTHONPATH='src'
python -m trip_planner.web.app
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

### Option B: Terminal CLI Mode

```bash
trip-planner
# or: python -m trip_planner.main
```

You will be prompted for:
1. **Departing from** (e.g. `Bengaluru`, `Delhi NCR`, `Mumbai`)
2. **Candidate cities** (e.g. `Manali, Munnar, Goa`)
3. **Interests** (e.g. `nature, waterfalls, street food, temples`)
4. **Trip length in days** (e.g. `5`)
5. **Total budget** (e.g. `25000` INR)

The terminal will stream agent execution and print a validated, structured `TripItinerary` JSON.

---

## 🧪 Testing

Run the automated test suite to verify agent configurations, task wiring, and schema validation:

```bash
pytest tests/ -v
```

Tests cover deterministic pipeline wiring, tool attachments, and Pydantic validation contracts without making paid network calls.

---

## 🗺️ Roadmap (Phase 2 — Planned, Not Yet Built)

The following features are planned for future releases:

- [ ] **🌍 Global Destination Mode**: Expanding scope to support international travel destinations outside India (the Global toggle in the web UI is currently locked in a disabled preview state, and the backend actively validates domestic-only requests for Phase 1).
- [ ] **💱 Dynamic Multi-Currency Engine**: Adding full multi-currency selection (`USD`, `EUR`, `GBP`) with real-time conversion rates.
- [ ] **📄 PDF & Calendar Export**: Exporting generated itineraries directly to styled PDF documents and `.ics` calendar files.
- [ ] **🚆 Live Transport APIs**: Integrating real-time IRCTC train availability and domestic flight pricing APIs.
- [ ] **⚡ Caching & Performance**: Adding a query cache layer to avoid repeated DuckDuckGo searches for identical queries.
