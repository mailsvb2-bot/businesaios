from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from time import monotonic
from typing import Callable, TypeVar

CANON_CONNECTOR_TIMEOUT_POLICY = True

_T = TypeVar('_T')


@dataclass(frozen=True)
class ConnectorTimeoutRule:
    operation: str
    timeout_seconds: float
    verify_timeout_seconds: float | None = None
    dry_run_timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if not str(self.operation or '').strip():
            raise ValueError('operation is required')
        if float(self.timeout_seconds) <= 0:
            raise ValueError('timeout_seconds must be > 0')
        if self.verify_timeout_seconds is not None and float(self.verify_timeout_seconds) <= 0:
            raise ValueError('verify_timeout_seconds must be > 0')
        if self.dry_run_timeout_seconds is not None and float(self.dry_run_timeout_seconds) <= 0:
            raise ValueError('dry_run_timeout_seconds must be > 0')


@dataclass(frozen=True)
class TimeoutDecision:
    operation: str
    timeout_seconds: float
    source: str
    clamped: bool = False


class ConnectorTimeoutPolicy:
    """Soft timeout policy for sync connectors.

    This policy bounds waiting time for a connector call. It does not hard-kill a
    blocked thread in CPython; that remains a process/runtime concern.
    """

    def __init__(
        self,
        *,
        default_timeout_seconds: float = 30.0,
        max_timeout_seconds: float = 300.0,
        rules: tuple[ConnectorTimeoutRule, ...] = (),
    ) -> None:
        if float(default_timeout_seconds) <= 0:
            raise ValueError('default_timeout_seconds must be > 0')
        if float(max_timeout_seconds) <= 0:
            raise ValueError('max_timeout_seconds must be > 0')
        if float(default_timeout_seconds) > float(max_timeout_seconds):
            raise ValueError('default_timeout_seconds must be <= max_timeout_seconds')
        self._default_timeout_seconds = float(default_timeout_seconds)
        self._max_timeout_seconds = float(max_timeout_seconds)
        self._rules: dict[str, ConnectorTimeoutRule] = {}
        for rule in rules:
            self.register(rule)

    def register(self, rule: ConnectorTimeoutRule) -> None:
        key = str(rule.operation).strip()
        if not key:
            raise ValueError('operation is required')
        self._rules[key] = rule

    def resolve(
        self,
        *,
        operation: str,
        verify: bool = False,
        dry_run: bool = False,
        requested_timeout: float | None = None,
    ) -> TimeoutDecision:
        op = str(operation or '').strip()
        if not op:
            raise ValueError('operation is required')
        if requested_timeout is not None:
            timeout = float(requested_timeout)
            if timeout <= 0:
                raise ValueError('requested_timeout must be > 0')
            clamped = timeout > self._max_timeout_seconds
            return TimeoutDecision(operation=op, timeout_seconds=min(timeout, self._max_timeout_seconds), source='request', clamped=clamped)
        rule = self._rules.get(op)
        if rule is None:
            return TimeoutDecision(operation=op, timeout_seconds=self._default_timeout_seconds, source='default', clamped=False)
        timeout = float(rule.timeout_seconds)
        source = 'operation_rule'
        if verify and rule.verify_timeout_seconds is not None:
            timeout = float(rule.verify_timeout_seconds)
            source = 'verify_rule'
        elif dry_run and rule.dry_run_timeout_seconds is not None:
            timeout = float(rule.dry_run_timeout_seconds)
            source = 'dry_run_rule'
        clamped = timeout > self._max_timeout_seconds
        return TimeoutDecision(operation=op, timeout_seconds=min(timeout, self._max_timeout_seconds), source=source, clamped=clamped)

    def run(
        self,
        fn: Callable[[], _T],
        *,
        operation: str,
        verify: bool = False,
        dry_run: bool = False,
        requested_timeout: float | None = None,
    ) -> _T:
        decision = self.resolve(operation=operation, verify=verify, dry_run=dry_run, requested_timeout=requested_timeout)
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='connector-timeout')
        future = executor.submit(fn)
        timed_out = False
        try:
            return future.result(timeout=decision.timeout_seconds)
        except FuturesTimeoutError as exc:
            timed_out = True
            future.cancel()
            raise TimeoutError(
                f'connector operation timed out: operation={decision.operation} timeout_seconds={decision.timeout_seconds}'
            ) from exc
        finally:
            executor.shutdown(wait=not timed_out, cancel_futures=timed_out)

    def deadline(
        self,
        *,
        operation: str,
        verify: bool = False,
        dry_run: bool = False,
        requested_timeout: float | None = None,
    ) -> float:
        decision = self.resolve(operation=operation, verify=verify, dry_run=dry_run, requested_timeout=requested_timeout)
        return monotonic() + float(decision.timeout_seconds)


__all__ = [
    'CANON_CONNECTOR_TIMEOUT_POLICY',
    'ConnectorTimeoutPolicy',
    'ConnectorTimeoutRule',
    'TimeoutDecision',
]
