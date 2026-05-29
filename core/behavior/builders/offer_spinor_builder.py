from __future__ import annotations

from datetime import UTC, datetime

from core.behavior.contracts.micro_spinor import MicroSpinor
from core.behavior.math.aggregation import aggregate_spinors
from core.behavior.math.complex4 import Complex4


def build_offer_spinor(entity_id: str, offer_ref: str, source_spinors: list[MicroSpinor]) -> MicroSpinor:
    now = datetime.now(UTC)
    psi = aggregate_spinors([Complex4(s.psi_re, s.psi_im) for s in source_spinors])
    return MicroSpinor(
        spinor_id=f"offer:{entity_id}:{offer_ref}",
        entity_id=entity_id,
        scope_type="offer",
        scope_ref=offer_ref,
        started_at=source_spinors[0].started_at if source_spinors else now,
        ended_at=source_spinors[-1].ended_at if source_spinors else now,
        psi_re=psi.re,
        psi_im=psi.im,
        amplitude=psi.magnitude(),
        phase=psi.phase(),
        source_event_refs=tuple(ref for s in source_spinors for ref in s.source_event_refs),
        operator_trace=tuple(op for s in source_spinors for op in s.operator_trace),
    )
