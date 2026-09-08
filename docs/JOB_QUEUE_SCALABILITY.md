# Job System & Background Worker Scalability Specification

## 1. Current Architecture: Process-Local Asyncio Semaphore

Trip generation tasks are orchestrated in the background using Python `asyncio` tasks governed by a process-local concurrency semaphore:

```python
# trip_planner/api/app.py
MAX_CONCURRENT_AI_JOBS = int(os.getenv("MAX_CONCURRENT_AI_JOBS", "2"))
ai_concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_AI_JOBS)
```

### Execution Flow:
1. Client submits `POST /api/plan-trip`.
2. Deterministic request hashing validates against duplicate in-flight requests.
3. Client rate limiter verifies maximum 1 active generation per client IP / authenticated user.
4. Database records a new job with `status="pending"`.
5. Background worker (`_execute_trip_job`) acquires the semaphore:
   - If $\ge 2$ AI jobs are currently active, incoming jobs wait cleanly in the FIFO semaphore queue.
   - CrewAI + LiteLLM orchestrates the multi-agent trip pipeline.
   - Semaphore is released in a `finally` block, ensuring zero resource leaks.

> [!WARNING]
> **Process-Local Limitation**:
> The `asyncio.Semaphore` operates strictly within a single Python OS process. If the service is scaled to multiple containers or Railway replicas behind a round-robin load balancer, each replica will enforce its own local semaphore independently. In a multi-replica setup, total concurrency across the fleet equals `N_replicas * MAX_CONCURRENT_AI_JOBS`.

---

## 2. Resource Footprint & Worker Envelope

Empirical profiling of the multi-agent CrewAI pipeline reveals the following resource envelope:

| Resource Metric | Value Range / Measurement | Operational Implication |
|:---|:---|:---|
| **Base Application Footprint** | ~120 MB RSS | FastAPI, Uvicorn, and loaded modules |
| **Memory per Active CrewAI Job** | ~60 MB – 110 MB RSS | Agent state, prompt buffers, LiteLLM context |
| **Peak Memory at 2 Concurrent Jobs** | ~320 MB – 380 MB RSS | Well within Railway standard 512 MB – 1 GB RAM tier |
| **CPU Utilization per Job** | Low to moderate (~5-15%) | Network I/O bound (waiting on Groq LLM API responses) |
| **Default Safe Concurrency Limit** | **2 concurrent jobs** | Protects provider RPM/TPM and single-core event loop |

---

## 3. Zombie Job Reaper & Timeout Safeguards

To prevent orphaned or crashed background tasks from remaining in `pending` or `running` states indefinitely:
1. **Periodic Background Reaper**:
   - Runs every 120 seconds in `_zombie_job_reaper_worker()`.
   - Any job lingering in `pending` or `running` state with `created_at < (now - 1800)` (30 minutes) is deterministically transitioned to `status="failed"` with `error="Job exceeded maximum execution time limit (30 minutes)."`.
2. **Server Restart Reconciliation**:
   - Upon application startup, `init_db()` automatically transitions any unfinished `pending`/`running` jobs from prior crashed instances to `failed`, preventing phantom pending jobs from locking clients.
3. **Bounded AI Execution Timeout**:
   - HTTP requests to Groq via LiteLLM are bounded with strict 45-second network timeouts and maximum 3 retry attempts with jittered exponential backoff.

---

## 4. Measurable Triggers for Redis / Celery / RQ Migration

The current process-local job runner is intentionally chosen to avoid operational complexity (no Redis instances, no broker maintenance, no Celery worker daemons). Migration to an external queue (e.g. Redis + RQ or Celery) should be undertaken **only when**:

1. **Multi-Replica Workload Distribution**:
   - When scaling beyond 1 Railway container, an external broker is required so any worker replica can pull and process jobs submitted to any web replica.
2. **Worker Isolation (OOM & Memory Separation)**:
   - When memory pressure from AI tasks threatens the stability or response latency of HTTP endpoints (`/api/health`, `/api/metrics`, `/api/trip/...`).
3. **Distributed Job Cancellation**:
   - When users need to cancel running jobs across multiple hosts in real time.
4. **Queue Prioritization**:
   - When product requirements demand priority queues (e.g. premium/paid users bypass free-tier queues).
