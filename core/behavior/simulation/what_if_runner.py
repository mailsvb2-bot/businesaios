from __future__ import annotations

from core.behavior.math.complex4 import Complex4
from core.behavior.observables.person_observables import compute_person_observables
from core.behavior.simulation.sequence_spinor_builder import build_sequence_spinors
from core.behavior.simulation.what_if_plan import WhatIfPlan


def run_what_if_plan(psi: Complex4, plan: WhatIfPlan) -> dict[str, object]:
    micro_spinors = build_sequence_spinors("simulation", psi, list(plan.operator_keys))
    observables = compute_person_observables(micro_spinors)
    return {
        "plan_id": plan.plan_id,
        "micro_spinor_count": len(micro_spinors),
        "observables": observables,
    }
