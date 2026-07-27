from __future__ import annotations

import hashlib
import json

from core.behavior.dirac_behavior import Complex4, DiracBehaviorModel
from core.behavior.operator_catalogs import resolve_operator_context

GOLDEN_REPLAY_REVISION = "dirac-replay-v2-reviewed-2026-07-27"
EXPECTED_GOLDEN_HASH = (
    "8124ee1052ae7171a8ae92d3dfbc6bae55fb118b05aae0225fd49ccd51f02359"
)


def _round_obs(obs: dict) -> dict:
    return {
        key: round(value, 6) if isinstance(value, float) else value
        for key, value in obs.items()
    }


def _hash_payload(payload: dict) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _replay_payload() -> dict:
    events = [
        {
            "timestamp_ms": 1_000,
            "event_type": "ui_click",
            "payload": {
                "button": "start",
                "funnel_stage": "onboarding",
                "actor_role": "user",
            },
        },
        {
            "timestamp_ms": 5_000,
            "event_type": "offer_shown",
            "payload": {
                "offer_id": "basic",
                "funnel_stage": "consideration",
                "actor_role": "user",
            },
        },
        {
            "timestamp_ms": 9_000,
            "event_type": "paywall_opened",
            "payload": {
                "funnel_stage": "decision",
                "actor_role": "decision_maker",
            },
        },
        {
            "timestamp_ms": 12_000,
            "event_type": "purchase_attempt",
            "payload": {
                "method": "card",
                "funnel_stage": "decision",
                "actor_role": "finance",
            },
        },
        {
            "timestamp_ms": 15_000,
            "event_type": "purchase_success",
            "payload": {
                "amount": 9990,
                "currency": "RUB",
                "funnel_stage": "decision",
                "actor_role": "finance",
            },
        },
    ]
    model = DiracBehaviorModel()
    psi0 = Complex4.zeros().renormalize(target_norm=1.0)
    context = resolve_operator_context(
        product={"product_id": "organization_platform"},
        tenant_id="default",
    )
    context["tenant_id"] = "default"
    context["product_id"] = "organization_platform"
    context["policy_context"] = {
        "funnel_stage": "decision",
        "actor_role": "finance",
    }
    context["policy_denials"] = {}
    context["anti"] = 0.0
    psi, obs = model.evolve(
        psi=psi0,
        events=events,
        now_ms=20_000,
        context=context,
    )
    return {
        "psi_re": [round(value, 6) for value in psi.re],
        "psi_im": [round(value, 6) for value in psi.im],
        "obs": _round_obs(obs),
        "policy_denials": dict(context.get("policy_denials") or {}),
    }


def test_golden_replay_dirac_deterministic_snapshot() -> None:
    first_payload = _replay_payload()
    second_payload = _replay_payload()
    assert first_payload == second_payload
    assert GOLDEN_REPLAY_REVISION == "dirac-replay-v2-reviewed-2026-07-27"
    assert _hash_payload(first_payload) == EXPECTED_GOLDEN_HASH
