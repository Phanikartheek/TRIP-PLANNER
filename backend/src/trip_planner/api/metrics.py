"""
Thread-safe production observability metrics for Trip Planner.
Tracks throughput, latencies (avg, P50, P95, P99), error breakdowns,
provider rate limits, and job lifecycles without leaking secrets or PII.
"""

import threading
import time
from typing import Any


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_requests: int = 0
        self._successful_generations: int = 0
        self._failed_generations: int = 0
        self._provider_rate_limits: int = 0
        self._provider_timeouts: int = 0
        self._validation_failures: int = 0
        self._retries_total: int = 0
        self._expired_jobs: int = 0
        self._active_jobs: int = 0
        self._generation_durations: list[float] = []
        self._start_time: float = time.time()

    def record_request(self) -> None:
        with self._lock:
            self._total_requests += 1

    def record_generation_success(self, duration_sec: float) -> None:
        with self._lock:
            self._successful_generations += 1
            self._generation_durations.append(round(duration_sec, 2))
            if len(self._generation_durations) > 1000:
                self._generation_durations = self._generation_durations[-1000:]

    def record_generation_failure(self, category: str = "general") -> None:
        with self._lock:
            self._failed_generations += 1
            cat_lower = category.lower()
            if "rate_limit" in cat_lower or "429" in cat_lower:
                self._provider_rate_limits += 1
            elif "timeout" in cat_lower:
                self._provider_timeouts += 1
            elif "validation" in cat_lower:
                self._validation_failures += 1

    def record_provider_429(self) -> None:
        with self._lock:
            self._provider_rate_limits += 1

    def record_provider_timeout(self) -> None:
        with self._lock:
            self._provider_timeouts += 1

    def record_validation_failure(self) -> None:
        with self._lock:
            self._validation_failures += 1

    def record_retry(self) -> None:
        with self._lock:
            self._retries_total += 1

    def record_job_expired(self) -> None:
        with self._lock:
            self._expired_jobs += 1

    def set_active_jobs(self, count: int) -> None:
        with self._lock:
            self._active_jobs = max(0, count)

    def inc_active_jobs(self) -> None:
        with self._lock:
            self._active_jobs += 1

    def dec_active_jobs(self) -> None:
        with self._lock:
            if self._active_jobs > 0:
                self._active_jobs -= 1

    def _calculate_percentile(self, sorted_vals: list[float], percentile: float) -> float:
        if not sorted_vals:
            return 0.0
        k = (len(sorted_vals) - 1) * percentile
        f = int(k)
        c = f + 1
        if c < len(sorted_vals):
            return round(sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f]), 2)
        return round(sorted_vals[f], 2)

    def get_metrics_summary(self) -> dict[str, Any]:
        with self._lock:
            durations = sorted(self._generation_durations)
            dur_count = len(durations)
            avg_dur = round(sum(durations) / dur_count, 2) if dur_count > 0 else 0.0

            p50 = self._calculate_percentile(durations, 0.50)
            p95 = self._calculate_percentile(durations, 0.95)
            p99 = self._calculate_percentile(durations, 0.99)

            return {
                "uptime_seconds": round(time.time() - self._start_time, 1),
                "total_requests": self._total_requests,
                "successful_generations": self._successful_generations,
                "failed_generations": self._failed_generations,
                "active_jobs": self._active_jobs,
                "expired_jobs": self._expired_jobs,
                "provider_rate_limits": self._provider_rate_limits,
                "provider_timeouts": self._provider_timeouts,
                "validation_failures": self._validation_failures,
                "retries_total": self._retries_total,
                "latency_samples": dur_count,
                "generation_latency_seconds": {
                    "avg": avg_dur,
                    "p50": p50,
                    "p95": p95,
                    "p99": p99,
                    "min": durations[0] if dur_count > 0 else 0.0,
                    "max": durations[-1] if dur_count > 0 else 0.0,
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._total_requests = 0
            self._successful_generations = 0
            self._failed_generations = 0
            self._provider_rate_limits = 0
            self._provider_timeouts = 0
            self._validation_failures = 0
            self._retries_total = 0
            self._expired_jobs = 0
            self._active_jobs = 0
            self._generation_durations.clear()
            self._start_time = time.time()


# Global shared metrics registry instance
metrics = MetricsRegistry()
