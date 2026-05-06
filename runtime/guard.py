"""RuntimeGuard — executable law before side-effects. Protocols in guard_protocols."""

from __future__ import annotations

import logging
from typing import Any

from runtime.decision import DecisionEnvelope
from survival.controller import SurvivalVerdict

from runtime.enforcement.rate_limit import RuntimeActionRateLimiter
from runtime.enforcement.action_contracts import (
    validate_execute_plan_payload,
    validate_telegram_transport_payload,
)
from runtime.enforcement.idempotency_gate import verify_idempotency_gate as _verify_idempotency_gate
from runtime.enforcement.signature_gate import verify_signature_gate as _verify_signature_gate
from runtime.guard_execution_support import (
    execute_once_runtime,
    verify_production_runtime,
    verify_recovery_runtime,
)
from runtime.guard_helpers import build_action_contract_runtime, enforce_action_contract
from runtime.guard_init_support import init_production_mode, init_reference_mode
from runtime.guard_production import enforce_survival_gate
from runtime.guard_protocols import (
    MAX_REPLAY_MS,
    SUPPORTED_ENVELOPE_VERSION,
    DecisionEnvelopeRef,
    DecisionExpired,
    DecisionLedger,
    SignatureVerifier,
)
from runtime.guard_reference import commit_reference_execution, verify_and_lock_reference

logger = logging.getLogger("runtime.guard")

CANON_RUNTIME_GUARD_OWNER = True
CANON_NO_DECISION_LOGIC = True
CANON_FAIL_CLOSED_EXECUTION_GATE = True
_GUARD_SPLIT_HELPERS = (
    validate_execute_plan_payload,
    validate_telegram_transport_payload,
    _verify_idempotency_gate,
    _verify_signature_gate,
)

__all__ = [
    "CANON_FAIL_CLOSED_EXECUTION_GATE",
    "CANON_NO_DECISION_LOGIC",
    "CANON_RUNTIME_GUARD_OWNER",
    "MAX_REPLAY_MS",
    "DecisionEnvelopeRef",
    "DecisionExpired",
    "DecisionLedger",
    "RuntimeGuard",
    "SignatureVerifier",
    "SUPPORTED_ENVELOPE_VERSION",
]


class RuntimeGuard:
    """Executable law before any side-effect.

    Blocks:
      - verify(envelope)
      - execute_once(envelope)

    Invariant: this is the ONLY gate before effects.
    """

    def __init__(self, *args, **kwargs):
        """Support exactly two construction modes.

        1) Production mode (legacy):
           RuntimeGuard(keyring, ledger, schema_registry, *, event_log=None,
                        ttl_skew_ms=0, clock=None, survival_controller=None)

        2) Reference mode (canonical contract tests):
           RuntimeGuard(survival, ledger, verifier)

        Both modes enforce the same execution law ordering:
           verify(signature) -> idempotency check -> survival -> execute_once/mark -> side-effect
        """
        if self._looks_like_reference_mode(args):
            init_reference_mode(guard=self, args=args, kwargs=kwargs)
            return

        if len(args) < 3:
            raise TypeError(
                "RuntimeGuard requires either (survival, ledger, verifier) "
                "or (keyring, ledger, schema_registry, ...)"
            )

        init_production_mode(
            guard=self,
            args=args,
            kwargs=kwargs,
            build_action_contract_runtime=build_action_contract_runtime,
            rate_limiter_factory=RuntimeActionRateLimiter,
        )

    @staticmethod
    def _looks_like_reference_mode(args: tuple[Any, ...]) -> bool:
        if len(args) != 3:
            return False
        survival, _ledger, verifier = args
        return hasattr(survival, "evaluate") and hasattr(verifier, "verify")

    def _require_mode(self, expected: str, method_name: str) -> None:
        actual = getattr(self, "_mode", "production")
        if actual != expected:
            raise RuntimeError(f"{method_name} is only available in {expected} mode")

    # ========================================================
    # Reference-mode API (canonical sequence)
    # ========================================================

    def verify_and_lock(self, envelope: DecisionEnvelope) -> SurvivalVerdict:
        """Reference-mode: verify signature -> idempotency -> survival verdict."""
        self._require_mode("reference", "verify_and_lock")
        return verify_and_lock_reference(
            verifier=self._verifier,
            ledger=self._ledger,
            survival=self._survival,
            lock=self._lock,
            envelope=envelope,
        )

    def commit(self, envelope: DecisionEnvelope) -> None:
        """Reference-mode: mark executed AFTER successful side-effect."""
        self._require_mode("reference", "commit")
        commit_reference_execution(ledger=self._ledger, lock=self._lock, envelope=envelope)

    def _enforce_action_contract(self, *, action: str, payload: Any) -> None:
        enforce_action_contract(
            mode=getattr(self, "_mode", "production"),
            action_specs=self._action_specs,
            rate_limiter=self._rate_limiter,
            kill_switch=self._kill_switch,
            action=action,
            payload=payload,
        )

    def _enforce_survival_gate(self, env: Any) -> None:
        enforce_survival_gate(survival=self._survival, events=self._events, env=env)

    def verify(self, env: Any) -> None:
        verify_production_runtime(guard=self, env=env)

    def execute_once(self, env: Any) -> None:
        execute_once_runtime(guard=self, env=env)

    def verify_recovery(self, env: Any) -> None:
        """Verify envelope for crash-recovery effect delivery.

        Rationale:
          - Ledger may already be marked (crash between mark and effects).
          - We still require a fully valid envelope signature/payload/schema.
          - We additionally require that the ledger already contains decision_id.

        This keeps Decision Sovereignty while allowing recovery to finish
        delivery of side-effects.
        """
        verify_recovery_runtime(guard=self, env=env)
