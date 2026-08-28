"""
SQLite persistent job store for Trip Planner API.
Replaces in-memory dict storage with robust local database persistence.
"""

import json
import os
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
    # Ensure tables exist immediately
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            result TEXT,
            error TEXT,
            created_at REAL NOT NULL,
            job_type TEXT NOT NULL,
            qa_history TEXT,
            parent_job_id TEXT
        );
    """)
    conn.commit()
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """
    Initializes the jobs table and reconciles interrupted jobs from prior crashes/restarts.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # Startup reconciliation: any job left in 'pending' or 'running' status
        # when the server starts was killed during server shutdown/restart.
        cursor.execute("""
            UPDATE jobs
            SET status = 'failed',
                error = 'Job was interrupted by a server restart/crash.'
            WHERE status IN ('pending', 'running');
        """)
        conn.commit()


def create_job(
    job_id: str,
    job_type: str,
    status: str = "pending",
    parent_job_id: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Inserts or replaces a job record.
    """
    now = time.time()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO jobs (job_id, status, result, error, created_at, job_type, qa_history, parent_job_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (job_id, status, None, None, now, job_type, json.dumps([]), parent_job_id),
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
        }


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
