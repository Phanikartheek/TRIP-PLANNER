"""
Job Repository Abstraction Layer.
Decouples API routes from the underlying persistence technology (PostgreSQL vs SQLite).
Routes interact strictly with the JobRepository interface.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from trip_planner.api import db


class JobRepository(ABC):
    """Abstract interface defining all job store operations."""

    @abstractmethod
    def create_job(
        self,
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
    ) -> dict[str, Any]:
        """Creates and stores a new job."""
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Retrieves a job by ID."""
        pass

    @abstractmethod
    def update_job(
        self,
        job_id: str,
        status: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        qa_history: list[dict[str, Any]] | None = None,
        checklist_state: list[dict[str, Any]] | None = None,
        travel_date: str | None = None,
        reminder_sent: bool | None = None,
        current_stage: str | None = None,
        progress_percentage: int | None = None,
        message: str | None = None,
        user_email: str | None = None,
    ) -> None:
        """Updates a job's status, result, error, progress stages, or metadata."""
        pass

    @abstractmethod
    def find_active_identical_job(
        self, client_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        """Finds any in-flight pending/running job with the exact same request hash for this user/client."""
        pass

    @abstractmethod
    def get_active_jobs_for_client(self, client_key: str) -> list[dict[str, Any]]:
        """Returns all currently pending or running jobs belonging to the client/session."""
        pass

    @abstractmethod
    def get_active_jobs_count(self) -> int:
        """Returns total count of pending and running jobs across the system."""
        pass

    @abstractmethod
    def reap_zombie_jobs(self, max_age_seconds: float = 900.0) -> list[str]:
        """Marks any pending/running jobs older than max_age_seconds as failed/expired."""
        pass

    @abstractmethod
    def list_user_jobs(self, email: str) -> list[dict[str, Any]]:
        """Lists completed trips for a given user email."""
        pass

    @abstractmethod
    def link_trip_to_user(self, job_id: str, user_email: str) -> bool:
        """Links an anonymous trip to an authenticated user account."""
        pass

    @abstractmethod
    def get_daily_usage(self, client_key: str, usage_date: str | None = None) -> int:
        """Returns the number of trips planned by a client on a given date."""
        pass

    @abstractmethod
    def increment_daily_usage(self, client_key: str, usage_date: str | None = None) -> int:
        """Increments and returns daily trips planned by a client."""
        pass


class SQLAlchemyJobRepository(JobRepository):
    """
    SQLAlchemy implementation supporting PostgreSQL and SQLite with pooling,
    multi-stage progress tracking, and daily usage tracking.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path

    def create_job(
        self,
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
    ) -> dict[str, Any]:
        return db.create_job(
            job_id=job_id,
            job_type=job_type,
            status=status,
            result=result,
            parent_job_id=parent_job_id,
            user_email=user_email,
            travel_date=travel_date,
            request_hash=request_hash,
            client_ip=client_ip,
            current_stage=current_stage,
            progress_percentage=progress_percentage,
            message=message,
            db_path=self.db_path,
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return db.get_job(job_id, db_path=self.db_path)

    def update_job(
        self,
        job_id: str,
        status: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        qa_history: list[dict[str, Any]] | None = None,
        checklist_state: list[dict[str, Any]] | None = None,
        travel_date: str | None = None,
        reminder_sent: bool | None = None,
        current_stage: str | None = None,
        progress_percentage: int | None = None,
        message: str | None = None,
        user_email: str | None = None,
    ) -> None:
        db.update_job(
            job_id=job_id,
            status=status,
            result=result,
            error=error,
            qa_history=qa_history,
            checklist_state=checklist_state,
            travel_date=travel_date,
            reminder_sent=reminder_sent,
            current_stage=current_stage,
            progress_percentage=progress_percentage,
            message=message,
            user_email=user_email,
            db_path=self.db_path,
        )

    def find_active_identical_job(
        self, client_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        return db.find_active_identical_job(
            client_key=client_key,
            request_hash=request_hash,
            db_path=self.db_path,
        )

    def get_active_jobs_for_client(self, client_key: str) -> list[dict[str, Any]]:
        return db.get_active_jobs_for_client(
            client_key=client_key,
            db_path=self.db_path,
        )

    def get_active_jobs_count(self) -> int:
        return db.get_active_jobs_count(db_path=self.db_path)

    def reap_zombie_jobs(self, max_age_seconds: float = 900.0) -> list[str]:
        return db.reap_zombie_jobs(max_age_seconds=max_age_seconds, db_path=self.db_path)

    def list_user_jobs(self, email: str) -> list[dict[str, Any]]:
        return db.get_user_trips(email=email, db_path=self.db_path)

    def link_trip_to_user(self, job_id: str, user_email: str) -> bool:
        return db.link_trip_to_user(job_id=job_id, user_email=user_email, db_path=self.db_path)

    def get_daily_usage(self, client_key: str, usage_date: str | None = None) -> int:
        return db.get_daily_usage(client_key=client_key, usage_date=usage_date, db_path=self.db_path)

    def increment_daily_usage(self, client_key: str, usage_date: str | None = None) -> int:
        return db.increment_daily_usage(client_key=client_key, usage_date=usage_date, db_path=self.db_path)


# Backward-compatible alias
SQLiteJobRepository = SQLAlchemyJobRepository

# Default global repository instance
default_job_repository = SQLAlchemyJobRepository()
