from __future__ import annotations

from typing import Any

from runtime.enforcement.idempotency_gate import emit_ledger_executed, mark_execution_once
from runtime.guard_helpers import verify_production_envelope
from runtime.guard_init_support import require_production_mode
from runtime.guard_production import enforce_survival_gate
from runtime.guard_protocols import MAX_REPLAY_MS, SUPPORTED_ENVELOPE_VERSION
from runtime.platform.config.env_flags import env_str


def verify_production_runtime(*, guard: Any, env: Any) -> None:
    mode = getattr(guard, "_mode", "production")
    require_production_mode(mode=mode, method_name="verify")
    verify_production_envelope(
        env=env,
        keyring=guard._keyring,
        schemas=guard._schemas,
        expected_issuer_id=guard._expected_issuer_id,
        supported_envelope_version=SUPPORTED_ENVELOPE_VERSION,
        max_replay_ms=MAX_REPLAY_MS,
        ttl_skew_ms=guard._ttl_skew_ms,
        now_ms=int(guard._clock.now_ms()),
        mode=mode,
        action_specs=guard._action_specs,
        rate_limiter=guard._rate_limiter,
        kill_switch=guard._kill_switch,
        run_mode=env_str("RUN_MODE", "").strip().lower(),
    )



def execute_once_runtime(*, guard: Any, env: Any) -> None:
    require_production_mode(mode=getattr(guard, "_mode", "production"), method_name="execute_once")
    verify_production_runtime(guard=guard, env=env)
    enforce_survival_gate(survival=guard._survival, events=guard._events, env=env)
    with guard._lock:
        mark_execution_once(ledger=guard._ledger, env=env)
    emit_ledger_executed(guard._events, env=env)



def verify_recovery_runtime(*, guard: Any, env: Any) -> None:
    require_production_mode(mode=getattr(guard, "_mode", "production"), method_name="verify_recovery")
    verify_production_runtime(guard=guard, env=env)
    if not hasattr(guard._ledger, "is_executed"):
        raise RuntimeError("LEDGER_MISSING_EXECUTED_CHECK")
    if not bool(guard._ledger.is_executed(env.decision.decision_id)):
        raise RuntimeError("RECOVERY_REQUIRES_LEDGER_MARK")
