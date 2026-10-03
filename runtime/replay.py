"""Canonical replay surfaces.

Recovery replay remains a bit-exact archive read. Historical evaluation reads
only the immutable state snapshot bound to the original Decision and delegates
challenger simulation to the canonical shadow evaluator. Neither path may
re-route production, execute effects, or query current business state.
"""

from __future__ import annotations

from typing import Any

from canon.anti_second_brain_rules import SHADOW_POLICY_MODULE_PREFIX
from contracts.tenant_identity import require_tenant_id
from core.policies.shadow import ShadowEvaluator
from core.utils.canonical import sha256_hex
from kernel.decision_crypto import (
    assert_envelope_signature_surface,
    load_keyring_secret,
    verify_signed_material,
)
from kernel.world_state import WorldStateV1, world_state_from_canonical_bytes
from runtime.decision import DecisionEnvelope

CANON_RUNTIME_REPLAY_THIN_SURFACE = True
CANON_RUNTIME_REPLAY_NO_DECISION_LOGIC = True
CANON_PHASE15_HISTORICAL_REPLAY = True
CANON_PHASE15_NO_FUTURE_LEAKAGE = True


class ReplayEngine:
    def __init__(self, decision_archive):
        self._archive = decision_archive

    def replay(self, decision_id: str) -> DecisionEnvelope:
        env = self._archive.get(decision_id)
        if env is None:
            raise KeyError(f"decision_not_found: {decision_id}")
        return env


class HistoricalReplayEngine:
    """Evaluate a challenger against the exact state used by a past Decision."""

    def __init__(
        self,
        decision_archive,
        snapshot_store,
        *,
        keyring: Any,
        policy_registry: Any,
        tenant_id: str,
        schemas: Any,
    ):
        self._archive = decision_archive
        self._snapshots = snapshot_store
        self._keyring = keyring
        self._policy_registry = policy_registry
        self._tenant_id = require_tenant_id(tenant_id)
        if not callable(getattr(schemas, "validate", None)):
            raise TypeError("HISTORICAL_REPLAY_SCHEMA_REGISTRY_REQUIRED")
        self._shadow = ShadowEvaluator(ledger=None, schemas=schemas)

    def replay_challenger(self, decision_id: str, candidate_policy_id: str) -> dict[str, Any]:
        env = self._archive.get(str(decision_id))
        if env is None:
            raise KeyError(f"decision_not_found: {decision_id}")
        assert_envelope_signature_surface(env)
        decision = env.decision
        try:
            secret = load_keyring_secret(keyring=self._keyring, kid=str(env.kid))
        except RuntimeError as exc:
            raise RuntimeError("HISTORICAL_REPLAY_SIGNATURE_UNVERIFIABLE") from exc
        if not verify_signed_material(
            decision=decision,
            payload_hash_value=str(env.payload_hash),
            signature=str(env.signature),
            secret=secret,
            kid=str(env.kid),
        ):
            raise RuntimeError("HISTORICAL_REPLAY_SIGNATURE_INVALID")
        decision_tenant_id = str(dict(decision.payload or {}).get("tenant_id") or "").strip()
        if not decision_tenant_id:
            raise RuntimeError("HISTORICAL_REPLAY_TENANT_ID_MISSING")
        if decision_tenant_id != self._tenant_id:
            raise RuntimeError("HISTORICAL_REPLAY_TENANT_SCOPE_MISMATCH")
        candidate_id = str(candidate_policy_id or "").strip()
        if not candidate_id:
            raise ValueError("HISTORICAL_REPLAY_CANDIDATE_ID_REQUIRED")
        resolver = getattr(self._policy_registry, "maybe_get", None)
        if not callable(resolver):
            raise TypeError("HISTORICAL_REPLAY_POLICY_REGISTRY_INVALID")
        candidate_policy = resolver(candidate_id)
        if candidate_policy is None:
            raise ValueError("HISTORICAL_REPLAY_CANDIDATE_NOT_REGISTERED")
        resolved_id = str(getattr(candidate_policy, "id", "") or "").strip()
        if resolved_id != candidate_id:
            raise ValueError("HISTORICAL_REPLAY_CANDIDATE_ID_MISMATCH")
        candidate_module = str(getattr(type(candidate_policy), "__module__", "") or "")
        if not candidate_module.startswith(SHADOW_POLICY_MODULE_PREFIX):
            raise ValueError("HISTORICAL_REPLAY_CANDIDATE_NOT_CANONICAL")

        snapshot = self._snapshots.get(str(decision.snapshot_id))
        if snapshot is None:
            raise RuntimeError("HISTORICAL_REPLAY_SNAPSHOT_MISSING")
        snapshot_bytes = bytes(snapshot)
        if sha256_hex(snapshot_bytes) != str(decision.state_hash):
            raise RuntimeError("HISTORICAL_REPLAY_SNAPSHOT_HASH_MISMATCH")

        state = _world_state_from_snapshot(snapshot_bytes)
        if int(state.schema_version) != int(decision.state_schema_version):
            raise RuntimeError("HISTORICAL_REPLAY_STATE_SCHEMA_MISMATCH")
        if state.canonical_bytes() != snapshot_bytes:
            raise RuntimeError("HISTORICAL_REPLAY_SNAPSHOT_NONCANONICAL")
        _assert_no_future_leakage(state=state, issued_at_ms=int(decision.issued_at_ms))
        _assert_identity_matches(state=state, payload=dict(decision.payload or {}))

        row = self._shadow.simulate(
            state=state,
            production_envelope=env,
            candidate_policy=candidate_policy,
        )
        if row is None or row.get("context_match") is not True:
            raise RuntimeError("HISTORICAL_REPLAY_CONTEXT_MISMATCH")
        return {
            **row,
            "historical_replay": True,
            "historical_source": "decision_snapshot",
            "decision_id": str(decision.decision_id),
            "snapshot_id": str(decision.snapshot_id),
            "decision_issued_at_ms": int(decision.issued_at_ms),
            "historical_state_timestamp_ms": int(state.timestamp_ms),
            "future_leakage": False,
        }


def _world_state_from_snapshot(snapshot_bytes: bytes) -> WorldStateV1:
    try:
        return world_state_from_canonical_bytes(snapshot_bytes)
    except ValueError as exc:
        raise RuntimeError("HISTORICAL_REPLAY_SNAPSHOT_INVALID") from exc


def _assert_no_future_leakage(*, state: WorldStateV1, issued_at_ms: int) -> None:
    if int(state.timestamp_ms) > int(issued_at_ms):
        raise RuntimeError("HISTORICAL_REPLAY_FUTURE_STATE")
    semantics = state.world_model_semantics
    if semantics is None:
        return
    if int(semantics.generated_at_ms) > int(issued_at_ms):
        raise RuntimeError("HISTORICAL_REPLAY_FUTURE_STATE")
    for record in semantics.records:
        if (
            int(record.occurred_at_ms) > int(issued_at_ms)
            or int(record.observed_at_ms) > int(issued_at_ms)
            or int(record.recorded_at_ms) > int(issued_at_ms)
        ):
            raise RuntimeError("HISTORICAL_REPLAY_FUTURE_STATE")


def _assert_identity_matches(*, state: WorldStateV1, payload: dict[str, Any]) -> None:
    tenant_id = str(payload.get("tenant_id") or "").strip()
    if tenant_id and tenant_id != str(state.tenant_id):
        raise RuntimeError("HISTORICAL_REPLAY_TENANT_MISMATCH")
    business_id = str(payload.get("business_id") or "").strip()
    state_business_id = str(
        dict(state.product or {}).get("business_id")
        or dict(state.meta or {}).get("business_id")
        or ""
    ).strip()
    if business_id and not state_business_id:
        raise RuntimeError("HISTORICAL_REPLAY_BUSINESS_ID_MISSING")
    if business_id and business_id != state_business_id:
        raise RuntimeError("HISTORICAL_REPLAY_BUSINESS_MISMATCH")

    semantics = state.world_model_semantics
    if semantics is None:
        return
    if tenant_id and str(semantics.tenant_id) != tenant_id:
        raise RuntimeError("HISTORICAL_REPLAY_SEMANTIC_TENANT_MISMATCH")
    if business_id and str(semantics.business_id) != business_id:
        raise RuntimeError("HISTORICAL_REPLAY_SEMANTIC_BUSINESS_MISMATCH")


__all__ = [
    "CANON_PHASE15_HISTORICAL_REPLAY",
    "CANON_PHASE15_NO_FUTURE_LEAKAGE",
    "CANON_RUNTIME_REPLAY_NO_DECISION_LOGIC",
    "CANON_RUNTIME_REPLAY_THIN_SURFACE",
    "HistoricalReplayEngine",
    "ReplayEngine",
]
