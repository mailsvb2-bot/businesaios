from __future__ import annotations

from runtime.integration.default_state_factories import (
    default_advisory_packet,
    default_architecture_state,
    default_diffusion_state,
    default_flow_state,
    default_market_snapshot,
    default_structure_state,
    default_user_observables,
)
from runtime.integration.degraded_note_builder import append_note, build_missing_input_note
from runtime.integration.fallback_policy import FallbackPolicy
from runtime.integration.missing_input_error import MissingIntegrationInputError


def resolve_input(*, value, name: str, allow_missing: bool, default_factory, notes: tuple[str, ...]):
    if value is not None:
        return value, notes
    if not allow_missing:
        raise MissingIntegrationInputError(f"missing required integration input: {name}")
    return default_factory(), append_note(notes, build_missing_input_note(name))


def resolve_user_observables(value, policy: FallbackPolicy, notes: tuple[str, ...]):
    return resolve_input(
        value=value,
        name="user_observables",
        allow_missing=policy.allow_missing_user_observables,
        default_factory=default_user_observables,
        notes=notes,
    )


def resolve_market_snapshot(value, policy: FallbackPolicy, notes: tuple[str, ...]):
    return resolve_input(
        value=value,
        name="market_snapshot",
        allow_missing=policy.allow_missing_market_snapshot,
        default_factory=default_market_snapshot,
        notes=notes,
    )


def resolve_architecture_state(value, policy: FallbackPolicy, notes: tuple[str, ...]):
    return resolve_input(value=value, name="architecture_state", allow_missing=policy.allow_missing_architecture_state, default_factory=default_architecture_state, notes=notes)


def resolve_structure_state(value, policy: FallbackPolicy, notes: tuple[str, ...]):
    return resolve_input(value=value, name="structure_state", allow_missing=policy.allow_missing_structure_state, default_factory=default_structure_state, notes=notes)


def resolve_flow_state(value, policy: FallbackPolicy, notes: tuple[str, ...]):
    return resolve_input(value=value, name="flow_state", allow_missing=policy.allow_missing_flow_state, default_factory=default_flow_state, notes=notes)


def resolve_diffusion_state(value, policy: FallbackPolicy, notes: tuple[str, ...]):
    return resolve_input(value=value, name="diffusion_state", allow_missing=policy.allow_missing_diffusion_state, default_factory=default_diffusion_state, notes=notes)


def resolve_advisory_packet(value, policy: FallbackPolicy, notes: tuple[str, ...]):
    return resolve_input(
        value=value,
        name="advisory_packet",
        allow_missing=policy.allow_missing_advisory_packet,
        default_factory=default_advisory_packet,
        notes=notes,
    )
