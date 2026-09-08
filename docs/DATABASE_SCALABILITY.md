# Database Scalability & Architecture Specification

## 1. Architectural Design: Repository Abstraction

The Trip Planner persistence layer follows a strict three-tier decoupled architecture:

```
[ FastAPI Endpoints ] (api/app.py)
         │
         ▼
[ JobRepository Interface ] (api/repository.py: JobRepository protocol)
         │
         ▼
[ SQLiteJobRepository Implementation ] (api/repository.py -> api/db.py)
         │
         ▼
[ SQLite WAL Database with ClosingConnection ] (jobs.db)
```

Routes interact strictly with `job_repo: JobRepository`, never directly issuing SQL statements. This ensures that swapping the backing store from SQLite to PostgreSQL or CockroachDB requires zero modifications to HTTP handlers, validation schemas, or background workers.

---

## 2. Current SQLite Configuration & Stability Safeguards

The active SQLite implementation incorporates the following production safeguards:

1. **Write-Ahead Logging (WAL)**:
   - Enabled on connection via `PRAGMA journal_mode=WAL;`.
   - Allows concurrent readers while a single writer is appending to the WAL file, eliminating read-write contention.
2. **Busy Timeout (30,000 ms)**:
   - Configured via `PRAGMA busy_timeout = 30000;`.
   - Prevents immediate `sqlite3.OperationalError: database is locked` errors during transient write spikes by allowing threads to back off and wait up to 30 seconds.
3. **ClosingConnection Resource Management**:
   - Every connection created via `get_connection()` subclasses `sqlite3.Connection` with an explicit `__exit__` context manager:
     ```python
     class ClosingConnection(sqlite3.Connection):
         def __exit__(self, exc_type, exc_val, exc_tb):
             try:
                 super().__exit__(exc_type, exc_val, exc_tb)
             finally:
                 self.close()
     ```
   - Automatically releases open file descriptors and OS lock handles immediately upon exiting `with` blocks.
4. **Schema Migrations**:
   - Dynamic non-destructive column checking (`PRAGMA table_info`) safely handles schema evolution (`request_hash`, `client_ip`, `checklist_state`, `reminder_sent`, `user_email`) across redeployments without table locks or data loss.

---

## 3. Measured Load Performance (Evidence-Backed)

Testing was conducted using a controlled load-test harness (`backend/tests/load_test.py`) with mock AI execution to isolate database and process-worker throughput:

| Concurrency Level | Total Requests | Success Rate | Submit P95 Latency | Job Completion P95 | SQLite Lock Contention Errors |
|:---|:---|:---|:---|:---|:---|
| **5 Concurrent Users** | 5 | 100% | 0.237 s | 0.751 s | 0 |
| **10 Concurrent Users** | 10 | 100% | 0.269 s | 1.358 s | 0 |
| **20 Concurrent Users** | 20 | 100% | 0.841 s | 2.783 s | 0 |

**Observations**:
- Across all 35 executed load-test jobs, zero `database is locked` errors occurred.
- P95 submission latency remained under 0.85 seconds even under a burst of 20 simultaneous submissions.
- Completion latency scaled predictably under the 2-worker process-local semaphore limit.

---

## 4. Measurable Triggers for PostgreSQL Migration

SQLite remains the optimal, zero-operational-overhead store for a single-container Railway deployment. **PostgreSQL migration should NOT be performed prematurely.** Migration should be triggered *only* when one or more of the following measurable thresholds are reached:

1. **Horizontal Container Scaling (Multi-Replica)**:
   - *Trigger*: Railway or Kubernetes deployment scales to $\ge 2$ web server containers.
   - *Reason*: SQLite is a single-host file-based database. Shared network volumes (such as NFS) introduce severe POSIX lock degradation and corruption risks with SQLite WAL.
2. **Sustained Lock Queuing**:
   - *Trigger*: P95 database lock wait latency exceeds 500 ms under normal traffic, or `sqlite3.BusyError` occurs $>0.01\%$ of the time despite the 30s busy timeout.
3. **High Sustained Concurrent Write Volume**:
   - *Trigger*: Sustained background writes exceed 100 writes/second continuously over a 15-minute window.
4. **Point-In-Time Recovery (PITR) & Streaming Replication**:
   - *Trigger*: Business recovery point objective (RPO) requires zero data loss with continuous write-ahead log archiving (e.g. AWS RDS or Supabase continuous archiving).
5. **Connection Pool Depletion**:
   - *Trigger*: Need for centralized connection pooling across multiple independent microservices.
