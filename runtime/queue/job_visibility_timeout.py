"""Visibility timeout policy for runtime queue jobs.

Operational contract only:
- how long a claimed job stays invisible
- when workers should heartbeat
- no scheduling or business decisions here
"""

from __future__ import annotations

from dataclasses import dataclass
from runtime.queue.job_contract import JobPriority, JobRecord

CANON_RUNTIME_QUEUE_JOB_VISIBILITY_TIMEOUT = True

@dataclass(frozen=True)
class JobVisibilityWindow:
    lease_seconds: int
    heartbeat_seconds: int


def _clamp(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


class JobVisibilityTimeout:
    def __init__(
        self,
        *,
        low_priority_lease_seconds: int = 30,
        normal_priority_lease_seconds: int = 60,
        high_priority_lease_seconds: int = 120,
        critical_priority_lease_seconds: int = 240,
        retry_extension_seconds: int = 15,
        retry_extension_cap_seconds: int = 180,
        min_lease_seconds: int = 15,
        max_lease_seconds: int = 900,
        min_heartbeat_seconds: int = 5,
        heartbeat_divisor: int = 3,
    ) -> None:
        self._low_priority_lease_seconds = max(1, int(low_priority_lease_seconds))
        self._normal_priority_lease_seconds = max(1, int(normal_priority_lease_seconds))
        self._high_priority_lease_seconds = max(1, int(high_priority_lease_seconds))
        self._critical_priority_lease_seconds = max(1, int(critical_priority_lease_seconds))
        self._retry_extension_seconds = max(0, int(retry_extension_seconds))
        self._retry_extension_cap_seconds = max(0, int(retry_extension_cap_seconds))
        self._min_lease_seconds = max(1, int(min_lease_seconds))
        self._max_lease_seconds = max(self._min_lease_seconds, int(max_lease_seconds))
        self._min_heartbeat_seconds = max(1, int(min_heartbeat_seconds))
        self._heartbeat_divisor = max(2, int(heartbeat_divisor))

    def lease_seconds_for(self, job: JobRecord) -> int:
        base = self._base_lease_for_priority(int(job.priority))
        retries_extension = min(
            max(0, int(job.attempts)) * self._retry_extension_seconds,
            self._retry_extension_cap_seconds,
        )
        return _clamp(
            base + retries_extension,
            minimum=self._min_lease_seconds,
            maximum=self._max_lease_seconds,
        )

    def heartbeat_seconds_for(self, job: JobRecord) -> int:
        lease_seconds = self.lease_seconds_for(job)
        heartbeat = max(self._min_heartbeat_seconds, lease_seconds // self._heartbeat_divisor)
        return min(heartbeat, max(1, lease_seconds - 1))

    def window_for(self, job: JobRecord) -> JobVisibilityWindow:
        return JobVisibilityWindow(
            lease_seconds=self.lease_seconds_for(job),
            heartbeat_seconds=self.heartbeat_seconds_for(job),
        )

    def _base_lease_for_priority(self, priority: int) -> int:
        if priority >= int(JobPriority.CRITICAL):
            return self._critical_priority_lease_seconds
        if priority >= int(JobPriority.HIGH):
            return self._high_priority_lease_seconds
        if priority <= int(JobPriority.LOW):
            return self._low_priority_lease_seconds
        return self._normal_priority_lease_seconds


__all__ = [
    "CANON_RUNTIME_QUEUE_JOB_VISIBILITY_TIMEOUT",
    "JobVisibilityTimeout",
    "JobVisibilityWindow",
]
