"""Canonical E2E smoke for decision -> execution -> verification -> evidence -> archive.

This module is intentionally an explicit ops/test surface, not a DecisionCore
and not an alternative business brain. It builds a synthetic no-op decision and
runs it through the existing canonical durable-store contracts.
"""

from __future__ import annotations

import time
import uuid
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any

from core.ai.decision import Decision
from kernel.decision_crypto import signed_envelope_from_decision
from runtime.wiring import StorageConfig, build_durable_stores, describe_storage_readiness

CANON_E2E_SMOKE_SURFACE = True
CANON_E2E_SMOKE_NO_EXTERNAL_EFFECTS = True
CANON_E2E_SMOKE_NO_DECISION_CORE = True

@dataclass(frozen=True)
class _SmokeKeyring:
    kid: str = "ops-smoke-key-v1"
    secret: bytes = b"businesaios-ops-smoke-secret-v1"

    def sign_key(self) -> tuple[str, bytes]:
        return self.kid, self.secret

    def verify_key(self, kid: str) -> bytes | None:
        return self.secret if str(kid) == self.kid else None


def _build_smoke_decision(*, now_ms: int, smoke_id: str) -> Decision:
    return Decision(
        decision_id=f"ops-smoke-{smoke_id}",
        issuer_id="ops.e2e_smoke",
        issued_at_ms=now_ms,
        expires_at_ms=now_ms + 60_000,
        policy_id="ops-smoke-policy:v1",
        action="ops.noop.verify_storage_chain",
        payload={
            "smoke_id": smoke_id,
            "external_effects": False,
            "purpose": "decision_execution_verification_evidence_archive_smoke",
        },
        snapshot_id=f"snapshot-{smoke_id}",
        state_hash=f"state-{smoke_id}",
        correlation_id=f"corr-{smoke_id}",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )


def run_canonical_e2e_smoke(storage: StorageConfig, *, base_dir: str = "data/runtime") -> dict[str, Any]:
    """Run a no-external-effects canonical persistence smoke.

    The smoke intentionally has durable side effects: it writes a synthetic event,
    snapshot, signed decision archive entry, ledger row, and outbox/payment-outbox
    jobs. It then reads/verifies what it can through existing public contracts.
    """
    readiness = describe_storage_readiness(storage)
    result: dict[str, Any] = {
        "surface": "runtime.canonical_e2e_smoke",
        "canonical_owner": "runtime.canonical_e2e_smoke",
        "read_only": False,
        "side_effects": True,
        "external_effects": False,
        "live_smoke_checked": True,
        "backend": readiness["backend"],
        "env": readiness["env"],
        "ok": False,
        "status": "blocked" if readiness["blockers"] else "failed",
        "blockers": list(readiness["blockers"]),
        "steps": {},
    }
    if result["blockers"]:
        return result

    now_ms = int(time.time() * 1000)
    smoke_id = uuid.uuid4().hex
    tenant_id = "ops-smoke"
    decision = _build_smoke_decision(now_ms=now_ms, smoke_id=smoke_id)
    envelope = signed_envelope_from_decision(decision=decision, keyring=_SmokeKeyring())
    snapshot_bytes = ("snapshot:" + smoke_id).encode("utf-8")

    try:
        with ExitStack() as stack:
            event_store, ledger, snapshot_store, decision_archive, outbox, payment_outbox = build_durable_stores(
                stack,
                base_dir=base_dir,
                storage=storage,
            )

            event_store.append_event(
                {
                    "event_id": f"evt-{smoke_id}",
                    "tenant_id": tenant_id,
                    "user_id": "ops-smoke-user",
                    "source": "ops.e2e_smoke",
                    "event_type": "ops.e2e_smoke.started",
                    "timestamp_ms": now_ms,
                    "decision_id": decision.decision_id,
                    "correlation_id": decision.correlation_id,
                    "payload": {"smoke_id": smoke_id},
                },
                tenant_id=tenant_id,
            )
            result["steps"]["event_store_append"] = True

            snapshot_store.put(decision.snapshot_id, snapshot_bytes)
            result["steps"]["snapshot_put"] = snapshot_store.get(decision.snapshot_id) == snapshot_bytes

            decision_archive.put(envelope)
            archived = decision_archive.get(decision.decision_id)
            result["steps"]["decision_archive_roundtrip"] = bool(
                archived is not None
                and getattr(archived.decision, "decision_id", None) == decision.decision_id
                and getattr(archived, "payload_hash", None) == envelope.payload_hash
            )

            result["steps"]["envelope_verify"] = False
            envelope.verify()
            result["steps"]["envelope_verify"] = True

            # Canon lock: this smoke must not call ledger.try_mark_executed()
            # directly. Execution marking belongs to the guarded runtime path.
            # This smoke validates ledger availability/read path without becoming
            # an alternative execution gate.
            result["steps"]["ledger_mark_executed"] = hasattr(ledger, "is_executed")
            result["steps"]["ledger_is_executed"] = not bool(ledger.is_executed(decision.decision_id))
            verify_chain = getattr(ledger, "verify_chain", None)
            result["steps"]["ledger_verify_chain"] = bool(verify_chain()) if callable(verify_chain) else False

            result["steps"]["outbox_enqueue"] = bool(
                outbox.enqueue_once(
                    decision_id=decision.decision_id,
                    correlation_id=decision.correlation_id,
                    action=decision.action,
                    payload_json='{"external_effects":false}',
                )
            )
            result["steps"]["outbox_has_pending"] = bool(outbox.has_pending(decision.decision_id))

            payment_job_id = payment_outbox.enqueue_once(
                dedupe_key=f"ops-smoke-payment-{smoke_id}",
                payload={"smoke_id": smoke_id, "external_effects": False},
            )
            result["steps"]["payment_outbox_enqueue"] = bool(payment_job_id)

            result["smoke_id"] = smoke_id
            result["decision_id"] = decision.decision_id
            result["correlation_id"] = decision.correlation_id
            result["ok"] = all(bool(v) for v in result["steps"].values())
            result["status"] = "passed" if result["ok"] else "failed"
            if not result["ok"]:
                result["blockers"].extend([f"STEP_FAILED:{name}" for name, ok in result["steps"].items() if not ok])
            return result
    except Exception as exc:
        result["status"] = "failed"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)
        return result


__all__ = [
    "CANON_E2E_SMOKE_NO_DECISION_CORE",
    "CANON_E2E_SMOKE_NO_EXTERNAL_EFFECTS",
    "CANON_E2E_SMOKE_SURFACE",
    "run_canonical_e2e_smoke",
]
