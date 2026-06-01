from __future__ import annotations

from core.behavior.contracts.micro_spinor import MicroSpinor
from core.behavior.math.complex4 import Complex4
from core.behavior.math.invariants import anti_field_from_magnitudes, coherence_from_spinors, engagement_from_spinor
from core.behavior.math.phases import oscillation_score, phase_stability
from core.behavior.math.vector_ops import clamp


def compute_person_observables(micro_spinors: list[MicroSpinor]) -> dict[str, float]:
    spinors = [Complex4(s.psi_re, s.psi_im) for s in micro_spinors]
    if not spinors:
        return {
            "intent_level": 0.0,
            "trust_level": 0.0,
            "value_recognition_level": 0.0,
            "payment_readiness_level": 0.0,
            "coherence_score": 0.0,
            "oscillation_score": 0.0,
            "phase_stability_score": 0.0,
            "anti_field_level": 0.0,
            "resonance_readiness": 0.0,
        }
    latest = spinors[-1]
    magnitudes = latest.magnitude()
    phases = [s.phase for s in micro_spinors]
    engagement = engagement_from_spinor(latest)
    coherence = coherence_from_spinors(spinors)
    anti = anti_field_from_magnitudes(magnitudes)
    oscillation = oscillation_score(phases)
    stability = phase_stability(phases)
    return {
        "intent_level": clamp(magnitudes[0]),
        "trust_level": clamp(magnitudes[1]),
        "value_recognition_level": clamp(magnitudes[2]),
        "payment_readiness_level": clamp(magnitudes[3]),
        "coherence_score": coherence,
        "oscillation_score": oscillation,
        "phase_stability_score": stability,
        "anti_field_level": anti,
        "engagement_level": engagement,
        "fragmentation_score": clamp(1.0 - coherence),
        "fatigue_score": clamp((oscillation + anti) / 2.0),
        "resonance_readiness": clamp((coherence + stability + magnitudes[3]) / 3.0),
        "timing_window_score": clamp((engagement + stability) / 2.0),
        "conversion_window_score": clamp((magnitudes[1] + magnitudes[2] + magnitudes[3]) / 3.0),
        "pressure_sensitivity": clamp((anti + (1.0 - magnitudes[1])) / 2.0),
        "offer_repulsion_score": clamp((anti + oscillation) / 2.0),
        "risk_amplification_score": clamp((1.0 - magnitudes[1]) * (1.0 - stability)),
        "intent_velocity": _velocity(micro_spinors, axis=0),
        "trust_velocity": _velocity(micro_spinors, axis=1),
        "readiness_velocity": _velocity(micro_spinors, axis=3),
        "anti_velocity": _anti_velocity(micro_spinors),
    }


def _velocity(micro_spinors: list[MicroSpinor], axis: int) -> float:
    if len(micro_spinors) < 2:
        return 0.0
    prev = micro_spinors[-2].amplitude[axis]
    last = micro_spinors[-1].amplitude[axis]
    return clamp((last - prev + 1.0) / 2.0)


def _anti_velocity(micro_spinors: list[MicroSpinor]) -> float:
    if len(micro_spinors) < 2:
        return 0.0
    prev = anti_field_from_magnitudes(micro_spinors[-2].amplitude)
    last = anti_field_from_magnitudes(micro_spinors[-1].amplitude)
    return clamp((last - prev + 1.0) / 2.0)
