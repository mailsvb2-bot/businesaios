from __future__ import annotations

from core.ai.decision_core import DecisionCore
from core.offers.engine import decide_offer
from core.offers.models import OfferRule, OfferSpec, OfferVariant


class DummyState:
    def __init__(self, *, user_id: str, behavior: dict | None = None, product: dict | None = None, economy: dict | None = None):
        self.user_id = str(user_id)
        self.behavior = behavior or {}
        self.product = product or {}
        self.economy = economy or {}


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
        world_model=None,
    )


def test_offer_decision_clamps_band_to_constraints() -> None:
    behavior = {"audio_completions": 1, "clicks_total": 20, "engagement_score": 1.0, "fatigue_index": 0.0}
    offer = OfferSpec(
        offer_id="o1",
        product_id="p1",
        variants=[OfferVariant(key="v1", title="T", body="B")],
        base_price_rub=990,
        rules=OfferRule(min_engagement=0.0, max_fatigue=1.0),
    )
    dec = decide_offer(offer=offer, user_id="u1", tenant_id="t1", behavior=behavior, max_band="low")
    assert dec is not None
    assert dec.band == "low"


def test_decision_core_sets_low_band_when_ltv_below_cac_ratio() -> None:
    core = _make_dc()
    state = DummyState(
        user_id="u_low",
        behavior={"clicks_total": 0, "audio_starts": 0},
        product={"economics": {"target_cac_rub": 600, "min_ltv_cac_ratio": 2.0}},
        economy={"predicted_ltv": 800},
    )
    assert core._allowed_price_band(state) == "low"
