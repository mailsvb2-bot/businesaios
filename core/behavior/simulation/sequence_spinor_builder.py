from __future__ import annotations

from datetime import UTC, datetime

from core.behavior.contracts.micro_spinor import MicroSpinor
from core.behavior.math.complex4 import Complex4
from core.behavior.operators.operator_application import apply_operator


def build_sequence_spinors(entity_id: str, initial_psi: Complex4, operator_keys: list[str]) -> list[MicroSpinor]:
    spinors: list[MicroSpinor] = []
    psi = initial_psi
    for idx, operator_key in enumerate(operator_keys):
        psi = apply_operator(psi, operator_key)
        ts = datetime.now(UTC)
        spinors.append(
            MicroSpinor(
                spinor_id=f"simulation:{entity_id}:{idx}",
                entity_id=entity_id,
                scope_type="simulation",
                scope_ref=operator_key,
                started_at=ts,
                ended_at=ts,
                psi_re=psi.re,
                psi_im=psi.im,
                amplitude=psi.magnitude(),
                phase=psi.phase(),
                source_event_refs=(str(idx),),
                operator_trace=(operator_key,),
            )
        )
    return spinors
