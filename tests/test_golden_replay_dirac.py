from __future__ import annotations

import hashlib
import json

from core.behavior.dirac_behavior import Complex4, DiracBehaviorModel
from core.behavior.operator_catalogs import resolve_operator_context


def _round_obs(obs: dict) -> dict:
    out = {}
    for k, v in obs.items():
        if isinstance(v, float):
            out[k] = round(v, 6)
        else:
            out[k] = v
    return out


def _hash_payload(payload: dict) -> str:
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_golden_replay_dirac_deterministic_snapshot() -> None:
    """A minimal deterministic replay of a single event trace.

    Goal:
      - Catch "second-line" divergences (alternate paths, hidden randomness)
      - Catch accidental policy wiring regressions (must stay bounded)
    """

    events = [
        {
            "timestamp_ms": 1_000,
            "event_type": "ui_click",
            "payload": {"button": "start", "funnel_stage": "onboarding", "actor_role": "user"},
        },
        {
            "timestamp_ms": 5_000,
            "event_type": "offer_shown",
            "payload": {"offer_id": "basic", "funnel_stage": "consideration", "actor_role": "user"},
        },
        {
            "timestamp_ms": 9_000,
            "event_type": "paywall_opened",
            "payload": {"funnel_stage": "decision", "actor_role": "decision_maker"},
        },
        {
            "timestamp_ms": 12_000,
            "event_type": "purchase_attempt",
            "payload": {"method": "card", "funnel_stage": "decision", "actor_role": "finance"},
        },
        {
            "timestamp_ms": 15_000,
            "event_type": "purchase_success",
            "payload": {"amount": 9990, "currency": "RUB", "funnel_stage": "decision", "actor_role": "finance"},
        },
    ]

    model = DiracBehaviorModel()
    psi0 = Complex4.zeros().renormalize(target_norm=1.0)
    ctx = resolve_operator_context(product={"product_id": "organization_platform"}, tenant_id="default")
    ctx["tenant_id"] = "default"
    ctx["product_id"] = "organization_platform"
    # provide policy context + telemetry holder (must not affect determinism)
    ctx["policy_context"] = {"funnel_stage": "decision", "actor_role": "finance"}
    ctx["policy_denials"] = {}
    ctx["anti"] = 0.0

    psi, obs = model.evolve(psi=psi0, events=events, now_ms=20_000, context=ctx)

    payload = {
        "psi_re": [round(x, 6) for x in psi.re],
        "psi_im": [round(x, 6) for x in psi.im],
        "obs": _round_obs(obs),
        "policy_denials": dict(ctx.get("policy_denials") or {}),
    }
    got = _hash_payload(payload)

    # This is intentionally strict: any change here must be a deliberate, reviewed update.
    expected = "01bdbe60597fdf0507a37ed3ba3fd1147e927a9be2f659f66525c791ada9905c"
    assert got == expected
