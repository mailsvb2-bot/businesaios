from __future__ import annotations

from config.routing_limits import MAX_RETRY_ATTEMPTS
from execution.primitives import StatusRetryPolicy


class LeadDeliveryRetry:
    def __init__(self, *, policy: StatusRetryPolicy | None = None) -> None:
        self._policy = policy or StatusRetryPolicy(terminal_status='ok', max_attempts=MAX_RETRY_ATTEMPTS)

    def should_retry(self, attempt: int, status: str) -> bool:
        return self._policy.should_retry(attempt=attempt, status=status)

    def run(self, operation):
        attempt = 0
        last = {'status': 'error', 'detail': 'retry exhausted'}
        while True:
            attempt += 1
            last = dict(operation())
            if not self.should_retry(attempt, str(last.get('status', 'error'))):
                return last
