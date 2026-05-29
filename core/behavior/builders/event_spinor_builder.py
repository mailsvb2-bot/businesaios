from __future__ import annotations

from datetime import datetime, timezone, UTC
from typing import Any, Mapping

from core.behavior.builders.base_spinor_factory import spinor_from_scores
from core.behavior.contracts.micro_spinor import MicroSpinor
from core.behavior.operators.operator_application import apply_operator


def build_event_spinor(event: Mapping[str, Any]) -> MicroSpinor:
    event_id = str(event.get("event_id", "unknown"))
    entity_id = str(event.get("entity_id", "unknown"))
    operator_key = str(event.get("event_type", "message_open"))
    started_at = event.get("timestamp") or datetime.now(UTC)
    if not isinstance(started_at, datetime):
        started_at = datetime.now(UTC)

    base = spinor_from_scores(
        float(event.get("intent_score", 0.4)),
        float(event.get("trust_score", 0.4)),
        float(event.get("value_score", 0.4)),
        float(event.get("payment_score", 0.3)),
    )
    psi = apply_operator(base, operator_key)
    return MicroSpinor(
        spinor_id=f"event:{event_id}",
        entity_id=entity_id,
        scope_type="event",
        scope_ref=operator_key,
        started_at=started_at,
        ended_at=started_at,
        psi_re=psi.re,
        psi_im=psi.im,
        amplitude=psi.magnitude(),
        phase=psi.phase(),
        source_event_refs=(event_id,),
        operator_trace=(operator_key,),
        context=dict(event),
    )
