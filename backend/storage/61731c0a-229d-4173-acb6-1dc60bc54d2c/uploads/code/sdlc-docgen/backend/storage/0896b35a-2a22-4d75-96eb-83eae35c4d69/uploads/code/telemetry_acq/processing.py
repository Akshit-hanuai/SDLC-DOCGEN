"""Health monitoring for the acquisition subsystem. Supports REQ-0002 (MTBF >= 2000 h)."""

from __future__ import annotations

import time


class HealthMonitor:
    """Tracks uptime and estimates MTBF (REQ-0002)."""

    def __init__(self, required_mtbf_hours: float = 2000.0) -> None:
        self.required_mtbf_hours = required_mtbf_hours
        self._started_at: float | None = None
        self._faults = 0

    def start(self) -> None:
        self._started_at = time.time()
        self._faults = 0

    def record_fault(self) -> None:
        self._faults += 1

    def mtbf_estimate_hours(self) -> float:
        if self._faults == 0 or self._started_at is None:
            return float("inf")
        return (time.time() - self._started_at) / 3600.0 / self._faults

    def within_spec(self) -> bool:
        return self.mtbf_estimate_hours() >= self.required_mtbf_hours
