from __future__ import annotations

from datetime import datetime

from core.behavior.contracts.micro_spinor import MicroSpinor
from core.behavior.math.aggregation import aggregate_spinors
from core.behavior.math.complex4 import Complex4


def build_window_spinor(
    entity_id: str,
    scope_ref: str,
    started_at: datetime,
    ended_at: datetime,
    source_spinors: list[MicroSpinor],
) -> MicroSpinor:
    psi = aggregate_spinors([Complex4(s.psi_re, s.psi_im) for s in source_spinors])
    return MicroSpinor(
        spinor_id=f"window:{entity_id}:{scope_ref}:{int(started_at.timestamp())}",
        entity_id=entity_id,
        scope_type="window",
        scope_ref=scope_ref,
        started_at=started_at,
        ended_at=ended_at,
        psi_re=psi.re,
        psi_im=psi.im,
        amplitude=psi.magnitude(),
        phase=psi.phase(),
        source_event_refs=tuple(ref for s in source_spinors for ref in s.source_event_refs),
        operator_trace=tuple(op for s in source_spinors for op in s.operator_trace),
    )
