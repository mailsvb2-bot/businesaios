from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import promotions as pm
from runtime.handler_impl.domains.business_flow_ops import handle_bookings

NOW = 1_800_000_000_000


def _brief(**kw) -> pm.Brief:
    base = dict(
        business_name="Анна",
        activity="психолог",
        offering_title="Консультация",
        offering_description="Разбор запроса",
        local_start="20.01 15:00",
        duration_min=60,
    )
    return pm.Brief(**{**base, **kw})


def test_candidates_are_domain_aware_and_guardrailed() -> None:
    cs = pm.candidates(_brief())
    assert [c.style for c in cs] == ["trust", "expert", "concise"]
    assert pm.best_creative(cs).creative_id.startswith("cr_")
    assert [c.style for c in pm.candidates(_brief(activity="сантехник", offering_title="Ремонт крана"))][
        0
    ] == "availability"
    bad = _brief(offering_title="ЛУЧШИЙ В МИРЕ", offering_description="100% гарантия", activity="x")
    assert all(pm.validate(c)[0] for c in pm.candidates(bad))
    assert pm.validate(pm.Creative("cr_0", "Ок", "вылечим всё", "d"))[1] == "medical_claims"
    assert pm.validate(pm.Creative("cr_0", "Ок", "Срочно!!!", "d"))[1] == "excessive_punctuation"


def test_tokens_payloads_and_public_url() -> None:
    assert pm.parse_start_payload("cpa_abcdefghijkl") == "abcdefghijkl"
    assert pm.parse_start_payload("cpa_bad") is None and pm.parse_start_payload("inv_x") is None
    assert (
        pm.public_url("https://ex.ru/b/", "abcdefghijkl")
        == "https://ex.ru/b/clientplatform/acquire?source=abcdefghijkl"
    )
    with pytest.raises(ValueError):
        pm.public_url("http://ex.ru", "abcdefghijkl")


def test_promote_open_once_and_book_with_attribution(flow) -> None:
    run = partial(flow.run, partial(handle_bookings, now_ms=NOW))
    run(op="add_slot", arg="2027-01-20 15:00 60 Разбор")
    _, text = run(op="promote", arg="1 vk")
    saved = flow.store.events[-1]["payload"]
    token = saved["source_token"]
    assert "[vk]" in text and f"/start cpa_{token}" in text
    run(op="promote", arg="1 vk")  # refresh keeps token and id
    assert flow.store.events[-1]["payload"]["source_token"] == token
    _, text = run(op="promo_open", arg=f"cpa_{token}", user_id="c1")
    assert f"/promo_book {token}" in text
    n = len(flow.store.events)
    run(op="promo_open", arg=f"cpa_{token}", user_id="c1")
    assert len(flow.store.events) == n  # repeat open records nothing
    _, text = run(op="promo_book", arg=token, user_id="c2")
    booked = flow.store.events[-1]["payload"]
    assert "Вы записаны" in text and booked["step"] == "booked" and booked["promotion_id"] == saved["promotion_id"]
    _, text = run(op="promotions")
    assert "открыли 2 · записались 1 · конверсия 50%" in text
    _, text = run(op="promo_book", arg=token, user_id="c3")
    assert "недоступно" in text
    assert "Не получилось" in run(op="promo_open", arg="cpa_zzzzzzzzzzzz")[1]


def test_start_deep_link_routes_to_promo_open() -> None:
    from types import SimpleNamespace

    from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes

    ctx = SimpleNamespace(callback_data="", callback_query_id="", cmd="/start", args="cpa_abcdefghijkl", is_admin=False)
    act = handle_business_flow_routes(ctx, user_id="u")
    assert act is not None


def test_candidates_fallback_when_profile_empty():
    from application.business_flows import promotions as pm
    import dataclasses
    fields = [f.name for f in dataclasses.fields(pm.Brief)]
    vals = {f: "" for f in fields}
    vals.update(offering_title="Промо", local_start="21.11 16:00", duration_min=60)
    cs = pm.candidates(pm.Brief(**vals))
    assert cs
    for c in cs:
        txt = " ".join(str(v) for v in dataclasses.asdict(c).values())
        assert "от\n" not in txt and ". ." not in txt and not txt.rstrip().endswith("от")
