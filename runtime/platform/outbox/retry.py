"""Outbox retry + dead-letter processing.

Deterministic orchestration layer:
- delivery execution still happens via RuntimeExecutor
- outbox is only state storage
- retry / dead-letter policy is delegated to reliability.dead_letter_policy
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from reliability.dead_letter_policy import DeadLetterPolicy
from reliability.outbox_store import OutboxMessage

MAX_RETRIES = DeadLetterPolicy().max_delivery_attempts


class OutboxLike(Protocol):
    def list_pending(self, *, limit: int = 100) -> Iterable[dict[str, Any]]: ...
    def claim(self, decision_id: str) -> bool: ...
    def mark_delivered(self, decision_id: str) -> None: ...
    def schedule_retry(self, decision_id: str, next_attempt_at_ms: int) -> None: ...
    def move_to_dead_letter(self, decision_id: str) -> None: ...


class ExecutorLike(Protocol):
    def execute_recovery(self, env): ...


@dataclass(frozen=True)
class RetryStats:
    processed: int = 0
    retried: int = 0
    dead: int = 0


def _item_id(item: dict[str, Any]) -> str:
    return str(item.get("decision_id") or item.get("id") or "")


def _item_attempts(item: dict[str, Any]) -> int:
    return int(item.get("retry_count") or item.get("attempts") or 0)


def _item_due_at_ms(item: dict[str, Any]) -> int | None:
    raw = item.get("next_attempt_at_ms")
    if raw is None:
        raw = item.get("run_after_ms")
    return None if raw is None else int(raw)


def _schedule_retry(*, outbox: Any, item_id: str, next_attempt_at_ms: int, error: str) -> None:
    try:
        outbox.schedule_retry(str(item_id), int(next_attempt_at_ms))
        return
    except TypeError:
        pass
    outbox.schedule_retry(str(item_id), after_ms=max(0, int(next_attempt_at_ms - int(datetime.now().timestamp() * 1000))), error=error)


def _move_to_dead_letter(*, outbox: Any, item_id: str, error: str) -> None:
    try:
        outbox.move_to_dead_letter(str(item_id))
        return
    except TypeError:
        pass
    outbox.move_to_dead_letter(str(item_id), error=error)


def _policy_message(*, item: dict[str, Any], now_ms: int) -> OutboxMessage:
    created_at_ms = int(item.get("created_at_ms") or now_ms)
    return OutboxMessage(
        tenant_id="default",
        message_id=_item_id(item) or "unknown",
        topic=str(item.get("action") or item.get("topic") or "runtime_recovery"),
        dedupe_key=str(item.get("decision_id") or item.get("dedupe_key") or _item_id(item) or "unknown"),
        payload=dict(item.get("payload") or {}),
        created_at=datetime.fromtimestamp(created_at_ms / 1000.0, tz=datetime.now().astimezone().tzinfo),
        updated_at=datetime.fromtimestamp(now_ms / 1000.0, tz=datetime.now().astimezone().tzinfo),
        available_at=datetime.fromtimestamp((_item_due_at_ms(item) or now_ms) / 1000.0, tz=datetime.now().astimezone().tzinfo),
        delivery_attempts=_item_attempts(item),
        last_error=None if item.get("last_error") is None else str(item.get("last_error")),
    )


def process_outbox(*, now: datetime, outbox: OutboxLike, executor: ExecutorLike, archive, limit: int = 100) -> RetryStats:
    processed = retried = dead = 0
    now_ms = int(now.timestamp() * 1000)
    dead_letter_policy = DeadLetterPolicy(max_delivery_attempts=MAX_RETRIES)

    for item in outbox.list_pending(limit=int(limit)):
        item_id = _item_id(item)
        if not item_id:
            continue
        next_attempt = _item_due_at_ms(item)
        if next_attempt is not None and int(next_attempt) > now_ms:
            continue
        if not outbox.claim(item_id):
            continue
        processed += 1
        try:
            env = archive.get(item_id) if hasattr(archive, "get") else archive.load(item_id)
            if env is None:
                raise RuntimeError("MISSING_ARCHIVED_ENVELOPE")
            executor.execute_recovery(env)
            outbox.mark_delivered(item_id)
        except Exception as exc:
            decision = dead_letter_policy.classify(
                message=_policy_message(item=item, now_ms=now_ms),
                error=exc,
                retryable=True,
                now=now,
            )
            if decision.move_to_dead_letter:
                _move_to_dead_letter(outbox=outbox, item_id=item_id, error=str(exc))
                dead += 1
            else:
                retry_at_ms = now_ms + int(decision.retry_delay_seconds or 0) * 1000
                _schedule_retry(outbox=outbox, item_id=item_id, next_attempt_at_ms=retry_at_ms, error=str(exc))
                retried += 1

    return RetryStats(processed=processed, retried=retried, dead=dead)
