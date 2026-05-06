from __future__ import annotations

from typing import Any

from runtime.boot import actions_registry
from runtime.enforcement.action_contracts import (
    extract_ids,
    require_idempotency_key,
    validate_execute_plan_payload,
    validate_telegram_transport_payload,
)
from runtime.enforcement.kill_switch_gate import enforce_kill_switch
from runtime.enforcement.rate_limit_gate import enforce_rate_limit
from runtime.enforcement.signature_gate import verify_signature_and_integrity


def build_action_contract_runtime(*, kwargs: dict[str, Any], rate_limiter_factory: Any) -> tuple[Any, Any, Any]:
    action_specs = kwargs.get("action_specs") or actions_registry
    rate_limiter = kwargs.get("rate_limiter") or rate_limiter_factory()
    kill_switch = kwargs.get("kill_switch")
    return action_specs, rate_limiter, kill_switch


def enforce_action_contract(*, mode: str, action_specs: Any, rate_limiter: Any, kill_switch: Any, action: str, payload: Any) -> None:
    if mode != "production":
        return
    spec = action_specs.get_spec(str(action))
    require_idempotency_key(spec=spec, payload=payload)
    tenant_id, user_id = extract_ids(payload)
    enforce_kill_switch(kill_switch=kill_switch, spec=spec, tenant_id=tenant_id, user_id=user_id)
    enforce_rate_limit(rate_limiter=rate_limiter, spec=spec, tenant_id=tenant_id, user_id=user_id)


def verify_production_envelope(
    *,
    env: Any,
    keyring: Any,
    schemas: Any,
    expected_issuer_id: str,
    supported_envelope_version: int,
    max_replay_ms: int,
    ttl_skew_ms: int,
    now_ms: int,
    mode: str,
    action_specs: Any,
    rate_limiter: Any,
    kill_switch: Any,
    run_mode: str,
) -> None:
    verify_signature_and_integrity(
        env=env,
        keyring=keyring,
        schemas=schemas,
        expected_issuer_id=expected_issuer_id,
        supported_envelope_version=supported_envelope_version,
        max_replay_ms=max_replay_ms,
        ttl_skew_ms=ttl_skew_ms,
        now_ms=now_ms,
    )
    enforce_action_contract(
        mode=mode,
        action_specs=action_specs,
        rate_limiter=rate_limiter,
        kill_switch=kill_switch,
        action=str(env.decision.action),
        payload=env.decision.payload,
    )
    validate_execute_plan_payload(
        action=str(env.decision.action),
        payload=env.decision.payload,
        schemas=schemas,
    )
    validate_telegram_transport_payload(
        action=str(env.decision.action),
        payload=env.decision.payload,
        run_mode=run_mode,
    )
