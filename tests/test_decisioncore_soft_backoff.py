from __future__ import annotations

from core.ai.decision_core import DecisionCore


class _Dummy:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _make_dc() -> DecisionCore:
    return DecisionCore(
        selector=_Dummy(select=lambda s: _Dummy(id="noop", propose=lambda st: _Dummy(steps=[], debug={}))),
        keyring=_Dummy(),
        schema_registry=_Dummy(validate=lambda a, p: "v1"),
        snapshot_store=_Dummy(),
        event_log=None,
        decision_archive=None,
        ttl_ms=1000,
        world_model=None,
        issuer_id="test",
    )


def test_decisioncore_allowed_price_band_guardrails_violation_forces_low() -> None:
    dc = _make_dc()
    state = _Dummy(behavior={"guardrails_violation": True}, product={})
    assert dc._allowed_price_band(state) == "low"


def test_decisioncore_merge_price_constraints_prefers_more_conservative_band() -> None:
    dc = _make_dc()
    merged = dc._merge_price_constraints(base={"max_band": "premium", "x": 1}, override={"max_band": "low", "mode": "safe"})
    assert merged["max_band"] == "low"
    assert merged["mode"] == "safe"
    assert merged["x"] == 1
