from __future__ import annotations

from functools import partial

from application.business_flows import admin as ad
from application.business_flows import bookings as bk
from application.business_flows import owner_panels as op_
from runtime.handler_impl.domains.business_flow_ops import handle_bookings

NOW = 1_800_000_000_000


def _run(flow, now=NOW, **kw):
    return partial(flow.run, partial(handle_bookings, now_ms=now))(**kw)


def test_safe_template_matches_donor_shape() -> None:
    t = op_.safe_template(title="Курс", description="  a   b ", schedule=("День 1: x", "День 2: y"))
    assert t.splitlines()[:5] == ["🎥 Курс", "", "📅 День 1: x", "День 2: y", ""]
    assert "a b" in t and t.endswith("напоминания для каждого дня.")


def test_attention_splits_failed_and_pending() -> None:
    s = bk.Slot("s", "T", NOW + 10 * 60_000, 60, status="booked", customer_id="c")
    # 15m reminder due 5 min ago -> pending; 3h due long ago -> failed
    failed, pending = op_.attention([(s, 15, ""), (s, 180, "")], now_ms=NOW)
    assert (failed, pending) == (1, 1)
    assert "нет" in op_.attention_text(0, 0)


def test_journey_attributes_promo_revenue() -> None:
    s = bk.Slot("s", "T", NOW, 60, status="booked", customer_id="c1")
    pay = ad.ManualPaymentRecord("p", "o", 5000, "RUB", "r", customer_id="c1")
    other = ad.ManualPaymentRecord("q", "o", 1000, "RUB", "r", customer_id="c9")

    class C:
        channel, booked = "vk", {"c1"}

    t = op_.journey_text(leads=3, slots={"s": s}, attendance={}, payments=[pay, other], camps={"x": C()}, reactivated=0)
    assert "Лиды: 3 → записи: 1 → пришли: нет подтверждённых данных → оплатили: 2" in t
    assert "Связано с источником: 50.00 RUB" in t and "Без подтверждённого источника: 10.00 RUB" in t
    assert "vk — 50.00 RUB · оплативших: 1" in t


def test_ad_channels_never_claim_connected() -> None:
    assert "подключён" not in op_.ad_channels_text(yandex_ready=True).replace("«подключено»", "")
    assert "OAuth" in op_.ad_channel_text(op_.ad_channel("yandex_direct", yandex_ready=True))
    assert "ads.telegram.org" in op_.ad_channel_text(op_.ad_channel("telegram_ads", yandex_ready=False))
    assert "нельзя подключить" in op_.setup_text("vk") and "никогда не отправляйте токен" in op_.setup_text("telegram")


def test_owner_panels_via_handler(flow) -> None:
    _run(flow, op="add_slot", arg="2027-01-20 15:00 Встреча")
    _run(flow, op="book", arg="1")
    n = len(flow.store.events)
    assert "Анонс готов" in _run(flow, op="announce", arg="1 Описание")[1]
    assert "Регистраций: 1" in _run(flow, op="event_promo", arg="1")[1]
    assert "Что требует внимания" in _run(flow, op="attention")[1]
    assert "Рекламные каналы" in _run(flow, op="ad_channels")[1]
    assert "Не получилось" in _run(flow, op="ad_channel", arg="nope")[1]
    assert "Деньги и путь клиента" in _run(flow, op="home_owner")[1]
    assert "Деньги и путь" not in _run(flow, op="home")[1]
    assert len(flow.store.events) == n  # read-only panels write no facts
