"""Canonical world-state packet enrichment helpers.

These helpers preserve domain semantics while keeping runtime integration
surfaces thin. They are pure domain transforms only: no runtime wiring,
no side effects, and no decision issuance.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from core.reward_bridge.reward_signal_builder import build_reward_signal
from runtime.explainability import build_reward_reasons, to_lines

CANON_WORLD_STATE_PACKET_ENRICHMENT = True
CANON_WORLD_STATE_PACKET_ENRICHMENT_PURE_DOMAIN = True


def _creative_metric(snapshot: object, field: str, default: float) -> float:
    try:
        value = getattr(snapshot, field)
    except Exception:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def build_reward_signal_from_world_view(
    *,
    creative_snapshots: Iterable[object],
    architecture_state: Mapping[str, float],
    structure_state: Mapping[str, float],
    flow_state: Mapping[str, float],
    market_snapshot: object,
    fallback_snapshot: object,
):
    snapshots = tuple(creative_snapshots)
    top_creative = snapshots[0] if snapshots else fallback_snapshot
    return build_reward_signal(
        snapshot=top_creative,
        architecture_global_stability=float(architecture_state.get("global_stability", 0.0)),
        blast_radius_risk=float(structure_state.get("blast_radius_risk", 0.0)),
        flow_turbulence=float(flow_state.get("turbulence", 0.0)),
        market_competitive_shift=float(getattr(market_snapshot, "global_competitive_shift", 0.0)),
    )


def build_advisory_notes(
    *,
    synthesized_state: object,
    advisory_packet: object,
    notes: tuple[str, ...],
    reward_signal: float,
) -> tuple[str, ...]:
    advisory_notes = tuple(getattr(advisory_packet, 'notes', ()))
    state_id = str(getattr(synthesized_state, 'state_id', 'unknown'))
    synthesis_note = f"state_synthesis:{state_id}"
    if synthesis_note not in advisory_notes:
        advisory_notes = (*advisory_notes, synthesis_note)
    conflicts = tuple(getattr(synthesized_state, 'conflicts', ()) or ())
    if conflicts:
        conflict_note = f"state_conflicts:{len(conflicts)}"
        if conflict_note not in advisory_notes:
            advisory_notes = (*advisory_notes, conflict_note)
    for note in notes:
        if note not in advisory_notes:
            advisory_notes = (*advisory_notes, note)
    reward_reason_lines = to_lines(build_reward_reasons(reward_signal))
    for line in reward_reason_lines:
        if line not in advisory_notes:
            advisory_notes = (*advisory_notes, line)
    return advisory_notes


__all__ = [
    'CANON_WORLD_STATE_PACKET_ENRICHMENT',
    'CANON_WORLD_STATE_PACKET_ENRICHMENT_PURE_DOMAIN',
    'build_advisory_notes',
    'build_reward_signal_from_world_view',
]
