from __future__ import annotations

import time

import pytest

from core.actions import build_schema_registry
from core.actions.action_names import ADS_APPLY_EXECUTE_V1
from core.ai.decision import Decision, DecisionEnvelope
from core.flags.provider import EnvFlagProvider
from core.safety.kill_switch import KillSwitch
from core.security.keyring import Keyring
from core.utils.canonical import payload_hash
from runtime.boot.actions_registry import ActionLimitsV1, ActionSpecV1
from runtime.enforcement.rate_limit import RuntimeActionRateLimiter
from runtime.guard import RuntimeGuard


class _MemoryLedger:
    def __init__(self):
        self._seen = set()

    def try_mark_executed(self, env: DecisionEnvelope) -> bool:
        did = str(env.decision.decision_id)
        if did in self._seen:
            return False
        self._seen.add(did)
        return True

    def is_executed(self, decision_id: str) -> bool:
        return str(decision_id) in self._seen

    def already_executed(self, decision_id: str) -> bool:
        return str(decision_id) in self._seen

    def mark_executed(self, decision_id: str) -> None:
        self._seen.add(str(decision_id))

    def verify_chain(self) -> bool:
        return True


class _TinyActionSpecs:
    def __init__(self):
        self._specs = {}

    def add(self, spec: ActionSpecV1) -> None:
        self._specs[str(spec.name)] = spec

    def get_spec(self, action: str) -> ActionSpecV1:
        if str(action) not in self._specs:
            raise KeyError(str(action))
        return self._specs[str(action)]


def _make_env(*, issuer_id: str, action: str, payload: dict, secret: bytes, kid: str, action_ver: int = 1) -> DecisionEnvelope:
    now = int(time.time() * 1000)
    dec = Decision(
        decision_id="d1",
        issuer_id=str(issuer_id),
        issued_at_ms=now,
        expires_at_ms=now + 60_000,
        policy_id="p1",
        action=str(action),
        payload=dict(payload),
        snapshot_id="s1",
        state_hash="h1",
        correlation_id="c1",
        state_schema_version=1,
        action_schema_version=int(action_ver),
        envelope_version=1,
    )
    ph = payload_hash(dec.payload)
    # signature verified elsewhere; for guard tests, we only need a consistent envelope structure.
    return DecisionEnvelope(decision=dec, payload_hash=ph, signature="sig", kid=str(kid), envelope_version=1)


def test_requires_idempotency_key_enforced(monkeypatch):
    schemas = build_schema_registry()
    secret = b"k"
    keyring = Keyring(keys={"k1": {"secret": secret}}, active_kid="k1")
    ledger = _MemoryLedger()

    specs = _TinyActionSpecs()
    specs.add(
        ActionSpecV1(
            name=ADS_APPLY_EXECUTE_V1,
            handler_ref="x",
            requires_idempotency_key=True,
            limits=ActionLimitsV1(kind="ads", per_tenant_per_min=999, per_user_per_min=999),
        )
    )

    guard = RuntimeGuard(
        keyring,
        ledger,
        schemas,
        expected_issuer_id="businesaios-core",
        action_specs=specs,
        rate_limiter=RuntimeActionRateLimiter(),
        kill_switch=KillSwitch(EnvFlagProvider()),
    )

    env = _make_env(
        issuer_id="businesaios-core",
        action=ADS_APPLY_EXECUTE_V1,
        payload={"tenant_id": "t1", "user_id": "u1"},
        secret=secret,
        kid="k1",
        action_ver=1,
    )

    with pytest.raises(RuntimeError) as e:
        guard._enforce_action_contract(action=str(env.decision.action), payload=env.decision.payload)
    assert "MISSING_IDEMPOTENCY_KEY" in str(e.value)


def test_rate_limit_enforced_per_user(monkeypatch):
    schemas = build_schema_registry()
    secret = b"k"
    keyring = Keyring(keys={"k1": {"secret": secret}}, active_kid="k1")
    ledger = _MemoryLedger()

    specs = _TinyActionSpecs()
    specs.add(
        ActionSpecV1(
            name="send_message@v1",
            handler_ref="x",
            requires_idempotency_key=True,
            limits=ActionLimitsV1(kind="general", per_tenant_per_min=999, per_user_per_min=1),
        )
    )

    limiter = RuntimeActionRateLimiter()
    guard = RuntimeGuard(
        keyring,
        ledger,
        schemas,
        expected_issuer_id="businesaios-core",
        action_specs=specs,
        rate_limiter=limiter,
        kill_switch=KillSwitch(EnvFlagProvider()),
    )

    payload = {"tenant_id": "t1", "user_id": "u1", "idempotency_key": "i1", "text": "hi"}
    guard._enforce_action_contract(action="send_message@v1", payload=payload)

    payload2 = {"tenant_id": "t1", "user_id": "u1", "idempotency_key": "i2", "text": "hi"}
    with pytest.raises(RuntimeError) as e:
        guard._enforce_action_contract(action="send_message@v1", payload=payload2)
    assert "RATE_LIMITED" in str(e.value)


def test_kill_switch_blocks_by_kind(monkeypatch):
    schemas = build_schema_registry()
    secret = b"k"
    keyring = Keyring(keys={"k1": {"secret": secret}}, active_kid="k1")
    ledger = _MemoryLedger()

    specs = _TinyActionSpecs()
    specs.add(
        ActionSpecV1(
            name="payments_charge@v1",
            handler_ref="x",
            requires_idempotency_key=True,
            limits=ActionLimitsV1(kind="payments", per_tenant_per_min=999, per_user_per_min=999),
        )
    )

    monkeypatch.setenv("FLAG_KILL_PAYMENTS", "1")
    guard = RuntimeGuard(
        keyring,
        ledger,
        schemas,
        expected_issuer_id="businesaios-core",
        action_specs=specs,
        rate_limiter=RuntimeActionRateLimiter(),
        kill_switch=KillSwitch(EnvFlagProvider()),
    )

    with pytest.raises(RuntimeError) as e:
        guard._enforce_action_contract(
            action="payments_charge@v1",
            payload={"tenant_id": "t1", "user_id": "u1", "idempotency_key": "i1"},
        )
    assert "KILL_SWITCHED" in str(e.value)
