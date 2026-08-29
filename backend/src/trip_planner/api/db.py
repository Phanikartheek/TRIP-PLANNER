"""
SQLite persistent job store and auth database for Trip Planner API.
Provides job persistence, user account management, magic-link token verification, and sessions.
"""

import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

# app.py -> api -> trip_planner -> src -> backend -> root
DEFAULT_DB_PATH = Path(os.environ.get("TRIP_PLANNER_DB_PATH", Path(__file__).resolve().parents[4] / "jobs.db"))


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    conn = sqlite3.connect(str(target_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")

    # Table 1: Jobs
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            result TEXT,
            error TEXT,
            created_at REAL NOT NULL,
            job_type TEXT NOT NULL,
            qa_history TEXT,
            parent_job_id TEXT,
            user_email TEXT
        );
    """)

    # Check if user_email column exists on pre-existing jobs table
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(jobs);")
    columns = [col["name"] for col in cursor.fetchall()]
    if "user_email" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN user_email TEXT;")

    # Table 2: Users
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            created_at REAL NOT NULL
        );
    """)

    # Table 3: Login Tokens (15 min TTL)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS login_tokens (
            token TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            expires_at REAL NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        );
    """)

    # Table 4: Sessions (7 days TTL)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_token TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            expires_at REAL NOT NULL
        );
    """)

    conn.commit()
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """
    Initializes database schemas and reconciles interrupted jobs from prior crashes/restarts.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET status = 'failed',
                error = 'Job was interrupted by a server restart/crash.'
            WHERE status IN ('pending', 'running');
        """)
        conn.commit()


# --- User & Auth Operations ---

def create_or_get_user(email: str, db_path: Path | str | None = None) -> dict[str, Any]:
    """Retrieves or creates a user record by email (lowercased)."""
    clean_email = email.strip().lower()
    now = time.time()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?;", (clean_email,))
        row = cursor.fetchone()
        if row:
            return {"email": row["email"], "created_at": row["created_at"]}

        cursor.execute("INSERT INTO users (email, created_at) VALUES (?, ?);", (clean_email, now))
        conn.commit()
        return {"email": clean_email, "created_at": now}


def create_login_token(email: str, ttl_seconds: int = 900, db_path: Path | str | None = None) -> str:
    """
    Generates a 256-bit cryptographically secure random token (secrets.token_urlsafe(32)),
    storing it with 15-minute expiration.
    """
    clean_email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + ttl_seconds
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO login_tokens (token, email, expires_at, used) VALUES (?, ?, ?, 0);",
            (token, clean_email, expires_at),
        )
        conn.commit()
    return token


def verify_and_consume_login_token(token: str, db_path: Path | str | None = None) -> str | None:
    """
    Validates a login token via direct SQLite Primary Key lookup ($O(1)$ constant time).
    Ensures the token is unused and not expired, creates/retrieves user, and marks token used.
    """
    now = time.time()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM login_tokens WHERE token = ? AND used = 0 AND expires_at > ?;",
            (token, now),
        )
        row = cursor.fetchone()
        if not row:
            return None

        email = row["email"]
        cursor.execute("UPDATE login_tokens SET used = 1 WHERE token = ?;", (token,))
        conn.commit()

        create_or_get_user(email, db_path=db_path)
        return email


def create_session(email: str, ttl_seconds: int = 604800, db_path: Path | str | None = None) -> str:
    """
    Generates a 256-bit cryptographically secure session token (secrets.token_urlsafe(32)),
    storing it with 7-day expiration.
    """
    clean_email = email.strip().lower()
    session_token = secrets.token_urlsafe(32)
    expires_at = time.time() + ttl_seconds
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (session_token, email, expires_at) VALUES (?, ?, ?);",
            (session_token, clean_email, expires_at),
        )
        conn.commit()
    return session_token


def get_session_email(session_token: str, db_path: Path | str | None = None) -> str | None:
    """
    Validates a session_token via direct SQLite Primary Key lookup ($O(1)$ constant time).
    Returns lowercased email if valid and not expired, else None.
    """
    if not session_token:
        return None
    now = time.time()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT email FROM sessions WHERE session_token = ? AND expires_at > ?;",
            (session_token, now),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return row["email"]


def delete_session(session_token: str, db_path: Path | str | None = None) -> None:
    """Invalidates a session record."""
    if not session_token:
        return
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_token = ?;", (session_token,))
        conn.commit()


# --- Job Operations ---

def create_job(
    job_id: str,
    job_type: str,
    status: str = "pending",
    parent_job_id: str | None = None,
    user_email: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Inserts or replaces a job record, optionally associating user_email.
    """
    now = time.time()
    clean_email = user_email.strip().lower() if user_email else None
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO jobs (job_id, status, result, error, created_at, job_type, qa_history, parent_job_id, user_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (job_id, status, None, None, now, job_type, json.dumps([]), parent_job_id, clean_email),
        )
        conn.commit()
    return {
        "job_id": job_id,
        "status": status,
        "result": None,
        "error": None,
        "created_at": now,
        "job_type": job_type,
        "qa_history": [],
        "parent_job_id": parent_job_id,
        "user_email": clean_email,
    }


def get_job(job_id: str, db_path: Path | str | None = None) -> dict[str, Any] | None:
    """
    Retrieves a job by job_id, deserializing JSON fields.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE job_id = ?;", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None

        result_data = json.loads(row["result"]) if row["result"] else None
        qa_history_data = json.loads(row["qa_history"]) if row["qa_history"] else []

        return {
            "job_id": row["job_id"],
            "status": row["status"],
            "result": result_data,
            "error": row["error"],
            "created_at": row["created_at"],
            "job_type": row["job_type"],
            "qa_history": qa_history_data,
            "parent_job_id": row["parent_job_id"],
            "user_email": row["user_email"] if "user_email" in row.keys() else None,
        }


def get_user_jobs(email: str, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    """
    Retrieves all completed jobs associated with a specific user email.
    """
    clean_email = email.strip().lower()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM jobs
            WHERE user_email = ? AND status = 'complete' AND job_type = 'plan'
            ORDER BY created_at DESC;
            """,
            (clean_email,),
        )
        rows = cursor.fetchall()
        user_jobs = []
        for row in rows:
            result_data = json.loads(row["result"]) if row["result"] else None
            user_jobs.append({
                "job_id": row["job_id"],
                "status": row["status"],
                "result": result_data,
                "created_at": row["created_at"],
                "user_email": row["user_email"],
            })
        return user_jobs


def update_job(
    job_id: str,
    status: str | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    qa_history: list[Any] | None = None,
    db_path: Path | str | None = None,
) -> None:
    """
    Updates mutable fields of an existing job record.
    """
    updates: list[str] = []
    params: list[Any] = []

    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if result is not None:
        updates.append("result = ?")
        params.append(json.dumps(result))
    if error is not None:
        updates.append("error = ?")
        params.append(error)
    if qa_history is not None:
        updates.append("qa_history = ?")
        params.append(json.dumps(qa_history))

    if not updates:
        return

    params.append(job_id)
    query = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?;"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        conn.commit()


def get_root_job(job_id: str, db_path: Path | str | None = None) -> dict[str, Any] | None:
    """
    Traverses parent_job_id pointers to find the root planning job for a session.
    """
    visited = set()
    current_id = job_id
    while current_id and current_id not in visited:
        visited.add(current_id)
        job = get_job(current_id, db_path=db_path)
        if not job:
            return None
        if not job.get("parent_job_id"):
            return job
        current_id = job["parent_job_id"]
    return None
