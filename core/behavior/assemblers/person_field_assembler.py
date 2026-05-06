from __future__ import annotations

from core.behavior.contracts.micro_spinor import MicroSpinor
from core.behavior.contracts.person_field import PersonField
from core.behavior.observables.person_observables import compute_person_observables


def assemble_person_field(entity_id: str, micro_spinors: list[MicroSpinor]) -> PersonField:
    observables = compute_person_observables(micro_spinors)
    return PersonField(
        entity_id=entity_id,
        micro_spinors=tuple(micro_spinors),
        stable_observables={
            "baseline_trust": observables.get("trust_level", 0.0),
            "baseline_value": observables.get("value_recognition_level", 0.0),
        },
        dynamic_observables=observables,
        structural_observables={
            "content_to_trust_coupling": observables.get("trust_level", 0.0),
            "trust_to_payment_coupling": observables.get("payment_readiness_level", 0.0),
        },
        temporal_observables={
            "phase_stability_score": observables.get("phase_stability_score", 0.0),
            "oscillation_score": observables.get("oscillation_score", 0.0),
        },
        market_relative_observables={},
    )
