from __future__ import annotations

import logging
import time
from typing import Any

from runtime.enforcement.world_model_pin_guard import enforce_world_model_pin_or_raise
from runtime.events.world_model_events import build_world_model_pin_check_event
from runtime.execution.executor_core import load_world
from runtime.observability import log_exception_throttled
from runtime.world_model import extract_pinned_world_model_meta_from_payload

LOGGER = logging.getLogger(__name__)


def check_and_emit_world_model_pin(*, event_log: Any, snapshot_store: Any, decision: Any, issuer_id: str) -> None:
    state = load_world(snapshot_store, str(decision.snapshot_id))
    user_id = str(getattr(state, "user_id", "unknown") if state is not None else "unknown")
    decision_id = str(decision.decision_id)
    pinned_meta = extract_pinned_world_model_meta_from_payload(getattr(decision, "payload", None) or {})
    pin_check = enforce_world_model_pin_or_raise(pinned_meta=pinned_meta, state=state)

    try:
        event = build_world_model_pin_check_event(
            decision_id=decision_id,
            user_id=user_id,
            check_result=pin_check.to_dict(),
            issuer_id=str(issuer_id or "runtime-executor"),
            timestamp_ms=int(time.time() * 1000),
        )
        if hasattr(event_log, "append"):
            event_log.append(event)
        elif hasattr(event_log, "emit"):
            event_log.emit(
                event_type=event.get("type", "decision.world_model_pin_checked"),
                source="runtime.executor",
                user_id=user_id,
                decision_id=decision_id,
                correlation_id=str(getattr(decision, "correlation_id", "") or ""),
                payload={"pin_check": pin_check.to_dict()},
            )
    except Exception as exc:
        log_exception_throttled(LOGGER, "runtime_executor_world_model_pin_event_failed", exc)
