# Security Audit & Hardening Specification

## 1. Executive Summary

This security audit verifies that the AI Trip Planner adheres to strict defense-in-depth principles across HTTP ingestion, AI agent boundaries, network proxying, and client rendering.

---

## 2. Reverse-Proxy & Client IP Trust

### Architecture:
Blindly trusting `X-Forwarded-For` allows malicious clients to spoof client IP addresses, bypassing rate limits and per-client concurrency locks.

### Implementation:
In `backend/src/trip_planner/api/app.py`:
```python
def get_trusted_client_ip(request: Request) -> str:
    trust_proxy = os.getenv("TRUST_PROXY", "").lower() in ("true", "1", "yes")
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_STATIC_URL"):
        trust_proxy = True

    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Client IP is the first untrusted IP from the left
            return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "127.0.0.1"
```
- **Local/Direct Mode**: Direct socket IP `request.client.host` is used. Spoofed headers are ignored.
- **Railway/Production Mode**: The ingress proxy terminates TLS and appends client IP to `X-Forwarded-For`. The first leftmost hop is extracted.

---

## 3. Request Ingestion & DoS Defense

1. **Request Body Size Limits**:
   - Middleware enforces a strict **1 MB (1,048,576 bytes)** cap on all incoming JSON request bodies.
   - Any attempt to submit oversized payloads immediately triggers `413 Payload Too Large` before deserialization.
2. **Slowloris & Timeout Protection**:
   - Uvicorn/FastAPI configured with bounded read/write timeouts.
3. **Endpoint Rate Limiting (SlowAPI)**:
   - `POST /api/plan-trip`: `10/minute`
   - `POST /api/revise-trip`: `15/minute`
   - `POST /api/ask-question`: `20/minute`
   - `POST /api/smart-request`: `15/minute`
   - `POST /api/auth/request-login`: `30/hour`
   - Active job lock: Maximum 1 active generation per client key (`user_email` or `client_ip`).

---

## 4. Input Validation & Prompt Injection Defense

1. **Pydantic Validation**:
   - `origin`, `cities`, `interests`: 1 to 300 characters, stripped, forbidden script tags.
   - `trip_length`: Integer bounded between 1 and 30 days.
   - `budget`: Positive float, maximum ₹10,000,000 (1 Crore INR).
   - `travelers`: Integer bounded between 1 and 20.
2. **Prompt Injection Boundaries**:
   - User inputs are passed into CrewAI as designated prompt variables enclosed in structured markdown blocks.
   - Agents are explicitly instructed with system guardrails to ignore instructions that attempt to alter agent role definitions or output raw internal system instructions.

---

## 5. Sensitive Data & Observability Protection

1. **Zero Secret Leakage in Metrics**:
   - The `/api/metrics` endpoint provides aggregated counts, P50/P95 latencies, and status tallies.
   - It is strictly scrubbed: no API keys, no bearer tokens, no prompts, no user emails, and no itinerary results.
   - Protected by optional `METRICS_TOKEN` environment variable.
2. **Clean Public Share Endpoint**:
   - `GET /api/trip/{job_id}/share` explicitly strips internal job metadata, including `user_email`, `qa_history`, and internal system timestamps.

---

## 6. Frontend XSS Protection

1. **Safe DOM Manipulation**:
   - Dynamic user-supplied text (cities, interests, question answers) is rendered using `textContent` and `innerText` rather than raw `innerHTML`.
2. **Calendar & PDF Escaping**:
   - Calendar (`.ics`) generation sanitizes CRLF injections and escapes commas, semicolons, and backslashes per RFC 5545.
