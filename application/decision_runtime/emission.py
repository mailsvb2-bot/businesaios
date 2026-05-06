from __future__ import annotations

import logging
import time
from typing import Any

from core.observability.throttled_logger import exception_throttled
from runtime.events.world_model_events import build_world_model_pinned_event

logger = logging.getLogger(__name__)


def archive_envelope(*, archive: Any, events: Any, env: Any, decision_id: str, user_id: str, correlation_id: str) -> None:
    if archive is None:
        return
    try:
        archive.put(env)
    except Exception as exc:  # noqa: BLE001
        exception_throttled(
            logger,
            key=f"archive_put|{decision_id}",
            msg=f"decision_core: archive.put failed decision={decision_id}",
        )
        try:
            if events is not None and hasattr(events, "emit"):
                events.emit(
                    event_type="decision_archive_failed",
                    source="decision_core",
                    user_id=user_id,
                    decision_id=decision_id,
                    correlation_id=correlation_id,
                    payload={"error": exc.__class__.__name__},
                )
        except Exception:  # noqa: BLE001
            exception_throttled(
                logger,
                key=f"archive_emit|{decision_id}",
                msg="decision_core: archive failure emit failed",
            )


def emit_decision_issued(*, events: Any, user_id: str, built: Any, tagged: Any, correlation_key: str | None) -> None:
    if events is None or not hasattr(events, "emit"):
        return
    events.emit(
        event_type="decision_issued",
        source="decision_core",
        user_id=user_id,
        decision_id=built.decision.decision_id,
        correlation_id=built.decision.correlation_id,
        payload={
            "policy_id": built.decision.policy_id,
            "action": built.decision.action,
            "payload_hash": built.payload_hash,
            "snapshot_id": built.decision.snapshot_id,
            "state_hash": built.decision.state_hash,
            "issued_at_ms": built.decision.issued_at_ms,
            "expires_at_ms": built.decision.expires_at_ms,
            "kid": built.envelope.kid,
            "envelope_version": built.decision.envelope_version,
            "state_schema_version": built.decision.state_schema_version,
            "action_schema_version": built.decision.action_schema_version,
            "correlation_key": correlation_key,
            "product_id": tagged.product_id,
            "domain": tagged.domain,
            "product_version": tagged.product_version,
        },
    )


def emit_world_model_pinned(*, events: Any, user_id: str, decision_id: str, correlation_id: str, world_model_meta: dict, issuer_id: str) -> None:
    try:
        event = build_world_model_pinned_event(
            decision_id=str(decision_id),
            user_id=str(user_id),
            world_model_meta=world_model_meta,
            issuer_id=issuer_id,
            timestamp_ms=int(time.time() * 1000),
        )
        if hasattr(events, "append"):
            events.append(event)
        elif hasattr(events, "emit"):
            events.emit(
                event_type=event.get("type", "decision.world_model_pinned"),
                source="decision_core",
                user_id=str(user_id),
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload={"world_model_meta": dict(world_model_meta)},
            )
    except Exception:  # noqa: BLE001
        exception_throttled(
            logger,
            key=f"{user_id}|world_model_pinned_event",
            msg="decision_core: failed to append world model pinned event",
        )


def emit_trace(*, events: Any, trace: Any, user_id: str, decision_id: str, correlation_id: str) -> None:
    try:
        tr = trace.build(decision_id=decision_id)
        events.emit(
            event_type="ai_decision_trace",
            source="decision_core",
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload=tr.to_dict(),
        )
    except Exception:  # noqa: BLE001
        exception_throttled(
            logger,
            key=f"trace_emit|{decision_id}",
            msg="decision_core: trace emit failed",
        )
