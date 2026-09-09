"""
Database access and persistence layer for Trip Planner API.
Supports PostgreSQL (via SQLAlchemy) with zero-config fallback to SQLite.
Provides persistent job tracking, multi-stage progress tracking, user authentication,
sessions, and daily rate-limiting usage tracking.
"""

import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
    func,
    or_,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database path resolution for SQLite
_db_path_env = os.environ.get("DATABASE_PATH") or os.environ.get("DB_PATH") or os.environ.get("TRIP_PLANNER_DB_PATH")
DEFAULT_DB_PATH = Path(_db_path_env) if _db_path_env else Path(__file__).resolve().parents[4] / "jobs.db"

Base = declarative_base()


class JobModel(Base):
    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True)
    status = Column(String(32), nullable=False, default="pending")
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(Float, nullable=False)
    job_type = Column(String(32), nullable=False, default="plan")
    qa_history = Column(Text, nullable=True, default="[]")
    parent_job_id = Column(String(64), nullable=True)
    user_email = Column(String(255), nullable=True, index=True)
    checklist_state = Column(Text, nullable=True)
    travel_date = Column(String(32), nullable=True)
    reminder_sent = Column(Integer, nullable=False, default=0)
    request_hash = Column(String(64), nullable=True, index=True)
    client_ip = Column(String(64), nullable=True, index=True)
    current_stage = Column(String(64), nullable=True, default="analyzing_request")
    progress_percentage = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)


class UserModel(Base):
    __tablename__ = "users"

    email = Column(String(255), primary_key=True)
    created_at = Column(Float, nullable=False)


class LoginTokenModel(Base):
    __tablename__ = "login_tokens"

    token = Column(String(64), primary_key=True)
    email = Column(String(255), nullable=False)
    expires_at = Column(Float, nullable=False)
    used = Column(Integer, nullable=False, default=0)


class SessionModel(Base):
    __tablename__ = "sessions"

    session_token = Column(String(64), primary_key=True)
    email = Column(String(255), nullable=False)
    expires_at = Column(Float, nullable=False)


class DailyUsageModel(Base):
    __tablename__ = "daily_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_key = Column(String(255), nullable=False, index=True)
    usage_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    plan_count = Column(Integer, nullable=False, default=0)


# Engine & Session Factory Cache
_engines: dict[str, Engine] = {}
_sessionmakers: dict[str, sessionmaker] = {}


def get_database_url(db_path: Path | str | None = None) -> str:
    """
    Determines the appropriate database connection URL.
    Prefers DATABASE_URL / POSTGRES_URL environment variables unless a custom SQLite db_path is provided.
    """
    if db_path is not None:
        p = Path(db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{p.resolve()}"

    env_pg_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if env_pg_url:
        clean_url = env_pg_url.strip()
        # Normalize postgres protocol for SQLAlchemy with psycopg3
        if clean_url.startswith("postgres://"):
            clean_url = clean_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif clean_url.startswith("postgresql://") and not clean_url.startswith("postgresql+"):
            clean_url = clean_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return clean_url

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DB_PATH.resolve()}"


def get_engine(db_path: Path | str | None = None) -> Engine:
    """Returns or creates a cached SQLAlchemy Engine instance."""
    url = get_database_url(db_path)
    if url not in _engines:
        if url.startswith("sqlite"):
            engine = create_engine(
                url,
                connect_args={"check_same_thread": False, "timeout": 30.0},
                pool_pre_ping=True,
            )

            @event.listens_for(engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                if isinstance(dbapi_connection, sqlite3.Connection):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    cursor.execute("PRAGMA busy_timeout=30000;")
                    cursor.close()

            _engines[url] = engine
        else:
            engine = create_engine(
                url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=300,
            )
            _engines[url] = engine

    return _engines[url]


def get_session_factory(db_path: Path | str | None = None) -> sessionmaker:
    """Returns or creates a cached sessionmaker for the target database."""
    url = get_database_url(db_path)
    if url not in _sessionmakers:
        engine = get_engine(db_path)
        Base.metadata.create_all(bind=engine)
        _sessionmakers[url] = sessionmaker(bind=engine, expire_on_commit=False)
    return _sessionmakers[url]


def dispose_engine(db_path: Path | str | None = None) -> None:
    """Disposes cached SQLAlchemy engine and its connection pool."""
    url = get_database_url(db_path)
    eng = _engines.pop(url, None)
    if eng:
        eng.dispose()
    _sessionmakers.pop(url, None)


class ClosingConnection(sqlite3.Connection):
    """
    SQLite connection wrapper that closes the connection and releases OS file locks
    upon exiting a context manager block, preventing connection leaks.
    """

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def get_connection(db_path: Path | str | None = None):
    """
    Provides a database connection.
    If using SQLite, returns a ClosingConnection with WAL mode for raw-cursor compatibility.
    If using PostgreSQL, returns an active SQLAlchemy connection context.
    """
    url = get_database_url(db_path)
    if url.startswith("sqlite"):
        target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target_path), timeout=30.0, factory=ClosingConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        return conn
    else:
        engine = get_engine(db_path)
        return engine.connect()


def init_db(db_path: Path | str | None = None) -> None:
    """
    Initializes database schemas and reconciles interrupted jobs from prior crashes/restarts.
    Adds missing columns to existing SQLite tables if schema evolved.
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(bind=engine)

    # If SQLite, ensure newer columns exist on legacy tables
    url = get_database_url(db_path)
    if url.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                res = conn.exec_driver_sql("PRAGMA table_info(jobs);")
                columns = [row[1] for row in res.fetchall()]
                missing_cols = {
                    "user_email": "TEXT",
                    "checklist_state": "TEXT",
                    "travel_date": "TEXT",
                    "reminder_sent": "INTEGER NOT NULL DEFAULT 0",
                    "request_hash": "TEXT",
                    "client_ip": "TEXT",
                    "current_stage": "TEXT DEFAULT 'analyzing_request'",
                    "progress_percentage": "INTEGER NOT NULL DEFAULT 0",
                    "message": "TEXT",
                }
                for col_name, col_type in missing_cols.items():
                    if col_name not in columns:
                        conn.exec_driver_sql(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type};")
                conn.commit()
        except Exception:
            pass

    # Reconcile interrupted jobs from server restarts
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        session.query(JobModel).filter(
            JobModel.status.in_(["pending", "running"])
        ).update(
            {
                JobModel.status: "failed",
                JobModel.error: "Job was interrupted by a server restart/crash.",
                JobModel.message: "Interrupted by server restart.",
            },
            synchronize_session=False,
        )
        session.commit()


# --- User & Auth Operations ---


def create_or_get_user(email: str, db_path: Path | str | None = None) -> dict[str, Any]:
    """Retrieves or creates a user record by email (lowercased)."""
    clean_email = email.strip().lower()
    now = time.time()
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        user = session.query(UserModel).filter(UserModel.email == clean_email).first()
        if user:
            return {"email": user.email, "created_at": user.created_at}

        new_user = UserModel(email=clean_email, created_at=now)
        session.add(new_user)
        session.commit()
        return {"email": clean_email, "created_at": now}


def create_login_token(email: str, ttl_seconds: int = 900, db_path: Path | str | None = None) -> str:
    """
    Generates a 256-bit cryptographically secure random token,
    storing it with 15-minute expiration.
    """
    clean_email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + ttl_seconds
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        tok_obj = LoginTokenModel(token=token, email=clean_email, expires_at=expires_at, used=0)
        session.add(tok_obj)
        session.commit()
    return token


def verify_and_consume_login_token(token: str, db_path: Path | str | None = None) -> str | None:
    """
    Validates a login token. Ensures the token is unused and not expired,
    creates/retrieves user, and marks token used.
    """
    now = time.time()
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        tok_obj = (
            session.query(LoginTokenModel)
            .filter(
                LoginTokenModel.token == token,
                LoginTokenModel.used == 0,
                LoginTokenModel.expires_at > now,
            )
            .first()
        )
        if not tok_obj:
            return None

        email = tok_obj.email
        tok_obj.used = 1
        session.commit()

        create_or_get_user(email, db_path=db_path)
        return email


def create_session(email: str, ttl_seconds: int = 604800, db_path: Path | str | None = None) -> str:
    """
    Generates a 256-bit cryptographically secure session token,
    storing it with 7-day expiration.
    """
    clean_email = email.strip().lower()
    session_token = secrets.token_urlsafe(32)
    expires_at = time.time() + ttl_seconds
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        sess_obj = SessionModel(
            session_token=session_token, email=clean_email, expires_at=expires_at
        )
        session.add(sess_obj)
        session.commit()
    return session_token


def get_session_email(session_token: str, db_path: Path | str | None = None) -> str | None:
    """
    Validates a session_token. Returns lowercased email if valid and not expired, else None.
    """
    if not session_token:
        return None
    now = time.time()
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        sess_obj = (
            session.query(SessionModel)
            .filter(
                SessionModel.session_token == session_token,
                SessionModel.expires_at > now,
            )
            .first()
        )
        if not sess_obj:
            return None
        return sess_obj.email


def delete_session(session_token: str, db_path: Path | str | None = None) -> None:
    """Invalidates a session record."""
    if not session_token:
        return
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        session.query(SessionModel).filter(
            SessionModel.session_token == session_token
        ).delete()
        session.commit()


# --- Job Operations ---


def _job_model_to_dict(job: JobModel) -> dict[str, Any]:
    """Converts a JobModel ORM object into a dictionary matching API expectations."""
    result_data = json.loads(job.result) if job.result else None
    qa_history_data = json.loads(job.qa_history) if job.qa_history else []
    checklist_data = json.loads(job.checklist_state) if job.checklist_state else None

    # Auto-initialize checklist from result packing_suggestions if NULL
    if checklist_data is None and result_data and isinstance(result_data, dict) and "packing_suggestions" in result_data:
        checklist_data = [{"item": str(s), "checked": False} for s in (result_data.get("packing_suggestions") or [])]

    return {
        "job_id": job.job_id,
        "status": job.status,
        "result": result_data,
        "error": job.error,
        "created_at": job.created_at,
        "job_type": job.job_type,
        "qa_history": qa_history_data,
        "parent_job_id": job.parent_job_id,
        "user_email": job.user_email,
        "checklist_state": checklist_data,
        "travel_date": job.travel_date,
        "reminder_sent": bool(job.reminder_sent) if job.reminder_sent is not None else False,
        "request_hash": job.request_hash,
        "client_ip": job.client_ip,
        "current_stage": job.current_stage or "analyzing_request",
        "progress_percentage": job.progress_percentage if job.progress_percentage is not None else 0,
        "message": job.message,
    }


def create_job(
    job_id: str,
    job_type: str,
    status: str = "pending",
    result: dict[str, Any] | None = None,
    parent_job_id: str | None = None,
    user_email: str | None = None,
    travel_date: str | None = None,
    request_hash: str | None = None,
    client_ip: str | None = None,
    current_stage: str | None = "analyzing_request",
    progress_percentage: int = 0,
    message: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Inserts or replaces a job record in the database.
    """
    now = time.time()
    clean_email = user_email.strip().lower() if user_email else None
    clean_travel_date = travel_date.strip() if travel_date else None
    clean_hash = request_hash.strip() if request_hash else None
    clean_ip = client_ip.strip() if client_ip else None
    result_json = json.dumps(result) if result else None

    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        existing = session.query(JobModel).filter(JobModel.job_id == job_id).first()
        if existing:
            existing.status = status
            existing.result = result_json
            existing.error = None
            existing.job_type = job_type
            existing.parent_job_id = parent_job_id
            existing.user_email = clean_email
            existing.travel_date = clean_travel_date
            existing.request_hash = clean_hash
            existing.client_ip = clean_ip
            existing.current_stage = current_stage
            existing.progress_percentage = progress_percentage
            existing.message = message
        else:
            new_job = JobModel(
                job_id=job_id,
                status=status,
                result=result_json,
                error=None,
                created_at=now,
                job_type=job_type,
                qa_history=json.dumps([]),
                parent_job_id=parent_job_id,
                user_email=clean_email,
                checklist_state=None,
                travel_date=clean_travel_date,
                reminder_sent=0,
                request_hash=clean_hash,
                client_ip=clean_ip,
                current_stage=current_stage,
                progress_percentage=progress_percentage,
                message=message,
            )
            session.add(new_job)
        session.commit()

    return {
        "job_id": job_id,
        "status": status,
        "result": result,
        "error": None,
        "created_at": now,
        "job_type": job_type,
        "qa_history": [],
        "parent_job_id": parent_job_id,
        "user_email": clean_email,
        "checklist_state": None,
        "travel_date": clean_travel_date,
        "reminder_sent": False,
        "request_hash": clean_hash,
        "client_ip": clean_ip,
        "current_stage": current_stage,
        "progress_percentage": progress_percentage,
        "message": message,
    }


def get_job(job_id: str, db_path: Path | str | None = None) -> dict[str, Any] | None:
    """Retrieves a job by job_id, deserializing JSON fields."""
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        job = session.query(JobModel).filter(JobModel.job_id == job_id).first()
        if not job:
            return None
        return _job_model_to_dict(job)


def find_active_identical_job(
    client_key: str, request_hash: str, db_path: Path | str | None = None
) -> dict[str, Any] | None:
    """
    Finds an in-flight (pending or running) job matching the exact request hash for this client/user.
    Guarantees one user's private job is never returned to another user.
    """
    if not request_hash or not client_key:
        return None
    clean_key = client_key.strip().lower()
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        job = (
            session.query(JobModel)
            .filter(
                JobModel.request_hash == request_hash,
                JobModel.status.in_(["pending", "running"]),
                or_(
                    func.lower(func.coalesce(JobModel.user_email, "")) == clean_key,
                    func.lower(func.coalesce(JobModel.client_ip, "")) == clean_key,
                ),
            )
            .order_by(JobModel.created_at.desc())
            .first()
        )
        if not job:
            return None
        return _job_model_to_dict(job)


def get_active_jobs_for_client(
    client_key: str, db_path: Path | str | None = None
) -> list[dict[str, Any]]:
    """Returns active (pending/running) jobs for a given client (by email or IP)."""
    if not client_key:
        return []
    clean_key = client_key.strip().lower()
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        jobs = (
            session.query(JobModel)
            .filter(
                JobModel.status.in_(["pending", "running"]),
                or_(
                    func.lower(func.coalesce(JobModel.user_email, "")) == clean_key,
                    func.lower(func.coalesce(JobModel.client_ip, "")) == clean_key,
                ),
            )
            .all()
        )
        return [_job_model_to_dict(j) for j in jobs]


def get_active_jobs_count(db_path: Path | str | None = None) -> int:
    """Returns the total number of jobs currently pending or running."""
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        count = (
            session.query(func.count(JobModel.job_id))
            .filter(JobModel.status.in_(["pending", "running"]))
            .scalar()
        )
        return int(count or 0)


def reap_zombie_jobs(
    max_age_seconds: float = 900.0, db_path: Path | str | None = None
) -> list[str]:
    """Reaps jobs stuck in pending/running for longer than max_age_seconds."""
    now = time.time()
    cutoff = now - max_age_seconds
    reaped_ids: list[str] = []
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        stuck_jobs = (
            session.query(JobModel)
            .filter(
                JobModel.status.in_(["pending", "running"]),
                JobModel.created_at < cutoff,
            )
            .all()
        )
        for j in stuck_jobs:
            j.status = "failed"
            j.error = "Job timed out and was expired by the runtime zombie reaper."
            j.message = "Job timed out."
            reaped_ids.append(j.job_id)
        session.commit()
    return reaped_ids


def get_user_jobs(email: str, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    """
    Retrieves all completed jobs (plan and revise) associated with a specific user email.
    """
    clean_email = email.strip().lower()
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        jobs = (
            session.query(JobModel)
            .filter(
                func.lower(JobModel.user_email) == clean_email,
                JobModel.status == "complete",
                JobModel.job_type.in_(["plan", "revise"]),
            )
            .order_by(JobModel.created_at.desc())
            .all()
        )
        return [_job_model_to_dict(j) for j in jobs]


# Alias for backward compatibility
get_user_trips = get_user_jobs


def update_job(
    job_id: str,
    status: str | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    qa_history: list[Any] | None = None,
    checklist_state: list[dict[str, Any]] | None = None,
    travel_date: str | None = None,
    reminder_sent: bool | None = None,
    current_stage: str | None = None,
    progress_percentage: int | None = None,
    message: str | None = None,
    user_email: str | None = None,
    db_path: Path | str | None = None,
) -> None:
    """Updates mutable fields of an existing job record."""
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        job = session.query(JobModel).filter(JobModel.job_id == job_id).first()
        if not job:
            return

        if status is not None:
            job.status = status
        if result is not None:
            job.result = json.dumps(result)
            if checklist_state is None and isinstance(result, dict) and "packing_suggestions" in result:
                checklist_state = [{"item": str(s), "checked": False} for s in (result.get("packing_suggestions") or [])]
        if error is not None:
            job.error = error
        if qa_history is not None:
            job.qa_history = json.dumps(qa_history)
        if checklist_state is not None:
            job.checklist_state = json.dumps(checklist_state)
        if travel_date is not None:
            job.travel_date = travel_date
        if reminder_sent is not None:
            job.reminder_sent = 1 if reminder_sent else 0
        if current_stage is not None:
            job.current_stage = current_stage
        if progress_percentage is not None:
            job.progress_percentage = max(0, min(100, progress_percentage))
        if message is not None:
            job.message = message
        if user_email is not None:
            job.user_email = user_email.strip().lower()

        session.commit()


def link_trip_to_user(job_id: str, user_email: str, db_path: Path | str | None = None) -> bool:
    """Associates an existing completed or active job with a user email."""
    if not job_id or not user_email:
        return False
    clean_email = user_email.strip().lower()
    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        job = session.query(JobModel).filter(JobModel.job_id == job_id).first()
        if not job:
            return False
        job.user_email = clean_email
        session.commit()
        return True


def get_checklist(job_id: str, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Retrieves current checklist state for a job, initializing from packing_suggestions if needed."""
    job = get_job(job_id, db_path=db_path)
    if not job:
        return []
    if job.get("checklist_state") is not None:
        return job["checklist_state"]
    result_data = job.get("result") or {}
    suggestions = result_data.get("packing_suggestions") or []
    checklist = [{"item": str(s), "checked": False} for s in suggestions]
    update_job(job_id, checklist_state=checklist, db_path=db_path)
    return checklist


def update_checklist_item(
    job_id: str, item: str, checked: bool, db_path: Path | str | None = None
) -> list[dict[str, Any]]:
    """Updates a single checklist item state in DB for a job and returns the full updated checklist."""
    checklist = get_checklist(job_id, db_path=db_path)
    found = False
    for el in checklist:
        if el.get("item") == item:
            el["checked"] = checked
            found = True
            break
    if not found:
        checklist.append({"item": item, "checked": checked})

    update_job(job_id, checklist_state=checklist, db_path=db_path)
    return checklist


def get_root_job(job_id: str, db_path: Path | str | None = None) -> dict[str, Any] | None:
    """Traverses parent_job_id pointers to find the root planning job for a session."""
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


# --- Rate Limiting & Daily Plan Quota Operations ---


def get_daily_usage(
    client_key: str, usage_date: str | None = None, db_path: Path | str | None = None
) -> int:
    """
    Returns the number of trips planned by a client_key (email or IP) on the specified date.
    usage_date format: 'YYYY-MM-DD' (defaults to current UTC date).
    """
    if not client_key:
        return 0
    clean_key = client_key.strip().lower()
    date_str = usage_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        rec = (
            session.query(DailyUsageModel)
            .filter(
                DailyUsageModel.client_key == clean_key,
                DailyUsageModel.usage_date == date_str,
            )
            .first()
        )
        return int(rec.plan_count) if rec else 0


def increment_daily_usage(
    client_key: str, usage_date: str | None = None, db_path: Path | str | None = None
) -> int:
    """
    Increments and returns the daily plan count for the client_key.
    usage_date format: 'YYYY-MM-DD' (defaults to current UTC date).
    """
    if not client_key:
        return 0
    clean_key = client_key.strip().lower()
    date_str = usage_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    session_factory = get_session_factory(db_path)
    with session_factory() as session:
        rec = (
            session.query(DailyUsageModel)
            .filter(
                DailyUsageModel.client_key == clean_key,
                DailyUsageModel.usage_date == date_str,
            )
            .first()
        )
        if rec:
            rec.plan_count += 1
            new_count = rec.plan_count
        else:
            new_count = 1
            rec = DailyUsageModel(client_key=clean_key, usage_date=date_str, plan_count=1)
            session.add(rec)
        session.commit()
        return new_count
