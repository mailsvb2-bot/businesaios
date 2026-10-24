from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import event_series as es
from runtime.handler_impl.domains.business_flow_ops import handle_bookings, handle_business_admin, handle_event_series

NOW = 1_800_000_000_000  # 2027-01-15 08:00 UTC
H, D = 3_600_000, 86_400_000


def _book(flow, slot_arg="2027-01-20 15:00 60 Разбор"):
    flow.run(partial(handle_bookings, now_ms=NOW), op="add_slot", arg=slot_arg)
    flow.run(partial(handle_bookings, now_ms=NOW), op="book", arg="1", user_id="u2")
    return next(e["payload"] for e in flow.store.events if e["payload"].get("step") == "slot_opened")


def _series(flow, now, **kw):
    return flow.run(partial(handle_event_series, now_ms=now), **kw)


def test_warmups_due_once_and_not_after_start(flow) -> None:
    slot = _book(flow)
    start = slot["starts_at_ms"]
    _series(flow, start - 3 * D + 1, op="dispatch")
    warm = [m for m in flow.effects.sent if m.get("user_id") == "u2" and "осталось" in m["text"]]
    assert len(warm) == 1 and "3 дня" in warm[0]["text"]
    _, text = _series(flow, start - 3 * D + 2, op="dispatch")
    assert "отправлено 0 из 0" in text
    _series(flow, start - D + 1, op="dispatch")
    _, text = _series(flow, start + 1, op="dispatch")
    assert "отправлено 0 из 0" in text


def test_followups_need_consent_attendance_and_offer_url(flow) -> None:
    slot = _book(flow)
    end = slot["starts_at_ms"] + 60 * 60_000
    _, text = _series(flow, end + H, op="dispatch")
    assert "offer_url" in text and "0 из 0" in text
    flow.run(handle_business_admin, op="setting", arg="offer_url = https://example.ru/offer")
    _series(flow, end + H, op="attendance", arg="1 attended")
    _, text = _series(flow, end + H, op="dispatch")
    assert "0 из 0" in text  # no opt-in yet
    _series(flow, end + H, op="offers_on", user_id="u2")
    _series(flow, end + H, op="dispatch")
    sent = flow.effects.sent[-2]
    assert sent["user_id"] == "u2" and "https://example.ru/offer" in sent["text"] and "/offers_off" in sent["text"]
    _series(flow, end + 25 * H, op="dispatch")
    assert "без искусственной срочности" in flow.effects.sent[-2]["text"]
    _series(flow, end + 25 * H, op="offers_off", user_id="u2")
    _, text = _series(flow, end + 49 * H, op="dispatch")
    assert "0 из 0" in text


def test_unknown_attendance_and_expired_window_send_nothing() -> None:
    from application.business_flows.bookings import Slot

    slot = Slot("s", "T", NOW, 60, "booked", "c")
    st = es.replay([es.consent("c", True)])
    assert es.due_messages(st, {"s": slot}, now_ms=NOW + 2 * H, offer_url="https://x") == []
    st.attendance[("s", "c")] = "no_show"
    assert len(es.due_messages(st, {"s": slot}, now_ms=NOW + 2 * H, offer_url="https://x")) == 1
    assert es.due_messages(st, {"s": slot}, now_ms=NOW + 5 * D, offer_url="https://x") == []


def test_owner_texts_validation_and_reset(flow) -> None:
    with pytest.raises(ValueError):
        es.set_text("warmup all 1 | Скидка по ссылке https://x")
    with pytest.raises(ValueError):
        es.set_text("followup attended_unpaid 1 | без ссылки")
    with pytest.raises(ValueError):
        es.set_text("followup no_show 3 | {offer}")
    _series(flow, NOW, op="text", arg="followup no_show 1 | Жаль, что не вышло: {offer}")
    _, text = _series(flow, NOW, op="preview")
    assert "followup no_show 1 (+1 ч, не пришли) [owner]: Жаль" in text
    _series(flow, NOW, op="reset", arg="followup no_show 1")
    assert "[owner]" not in _series(flow, NOW, op="preview")[1]
    _, text = _series(flow, NOW, op="warmup_days", arg="7, 1")
    assert "7, 1" in text


def test_attendance_only_for_past_bookings(flow) -> None:
    _book(flow)
    _, text = _series(flow, NOW, op="attendance", arg="1 attended")
    assert "Не получилось" in text


def test_channel_priority_and_pick():
    from application.business_flows import event_series as es
    assert es.channel_priority({}) == es.DEFAULT_CHANNEL_PRIORITY
    assert es.channel_priority({es.CHANNEL_PRIORITY_ENV: "Telegram, x, telegram,vk"}) == ("telegram", "vk")
    assert es.channel_priority({es.CHANNEL_PRIORITY_ENV: "bad"}) == es.DEFAULT_CHANNEL_PRIORITY
    assert es.pick_channel({"vk", "telegram"}, {"telegram"}, {}) == "telegram"
    assert es.pick_channel({"vk"}, {"telegram"}, {}) is None


def test_event_content_plan_and_visual_key():
    from application.business_flows import event_series as es
    f = [es.set_content_mode("e1", "warmup", "text_with_image")]
    plan = es.content_plan(es.replay(f), "e1")
    assert plan == {"warmup": "text_with_image", "event_day_announcement": "text", "post_event_followup": "text"}
    import pytest
    with pytest.raises(ValueError):
        es.set_content_mode("e1", "warmup", "gif")
    assert es.event_visual_idempotency_key(event_id="e1", stage="warmup", message_key="w:1") == "event:e1:warmup:w:1:image:v1"
    with pytest.raises(ValueError):
        es.event_visual_idempotency_key(event_id="e1", stage="warmup", message_key="bad key")


# ---- event visual assets, media outbox, e-mail target, stage visual (ports of event_content_assets/followups/warmups) ----
def _st(*facts):
    return es.replay(list(facts))


def test_asset_reference_revisions_cleanup_queue_and_batch_replay() -> None:
    st = _st()
    a1, f1 = es.set_asset_reference(st, event_id="e1", stage="warmup", slot_key="w1", kind="image",
                                    media_reference="/m/a.png", source="owner")
    assert a1["revision"] == 1
    st = _st(*f1)
    assert es.set_asset_reference(st, event_id="e1", stage="warmup", slot_key="w1", kind="image",
                                  media_reference="/m/a.png", source="owner")[1] == []  # same reference: no revision
    a2, f2 = es.set_asset_reference(st, event_id="e1", stage="warmup", slot_key="w1", kind="image",
                                    media_reference="/m/b.png", source="owner")
    assert a2["revision"] == 2 and f2[1] == {"step": "media_cleanup_queued", "reference": "/m/a.png",
                                             "reason": "superseded_event_content_asset"}
    st = _st(*f1, {"step": "batch", "facts": f2})  # batched facts replay like plain ones
    assert es.get_asset(st, "e1", "warmup", "w1")["media_reference"] == "/m/b.png" and es.get_asset(st, "e1", "warmup", "zz") is None
    for bad in (dict(kind="gif"), dict(stage="nope"), dict(slot_key="bad key"), dict(media_reference=" ")):
        with pytest.raises(ValueError):
            es.set_asset_reference(st, **{**dict(event_id="e1", stage="warmup", slot_key="w1", kind="image",
                                                 media_reference="/m/x", source="owner"), **bad})
    assert es.queue_replaced("", reason="x") == []


def test_generated_asset_is_stored_once_per_source_job() -> None:
    st = _st()
    a, f = es.store_generated_asset(st, event_id="e1", stage="warmup", slot_key="w1", kind="image",
                                    stored_reference="/store/1.png", source_ref="job1")
    st = _st(*f)
    again, f2 = es.store_generated_asset(st, event_id="e1", stage="warmup", slot_key="w1", kind="image",
                                         stored_reference="/store/1.png", source_ref="job1")
    assert f2 == [] and again["revision"] == a["revision"]


def test_active_visual_asset_requires_matching_content_mode() -> None:
    _, f = es.set_asset_reference(_st(), event_id="e1", stage="warmup", slot_key="w1", kind="image",
                                  media_reference="/m/a.png", source="owner")
    _, g = es.set_asset_reference(_st(), event_id="e1", stage="post_event_followup", slot_key="p1", kind="image",
                                  media_reference="/m/p.png", source="owner")
    assert es.active_warmup_visual_asset(_st(*f), event_id="e1", slot_key="w1") is None  # mode is text-only
    on = _st(*f, *g, es.set_content_mode("e1", "warmup", "text_with_image"),
             es.set_content_mode("e1", "post_event_followup", "text_in_image"))
    assert es.active_warmup_visual_asset(on, event_id="e1", slot_key="w1") == ("image", "/m/a.png", 1)
    assert es.active_followup_visual_asset(on, event_id="e1", slot_key="p1") == ("image", "/m/p.png", 1)
    video = _st(*f, es.set_content_mode("e1", "warmup", "text_with_video"))
    assert es.active_warmup_visual_asset(video, event_id="e1", slot_key="w1") is None  # image asset, video mode


def test_media_dispatch_keys_and_idempotent_outbox() -> None:
    k = es.warmup_media_dispatch_key(event_id="e1", registration_id="r1", slot_key="a:b", message_revision=2, asset_revision=3)
    assert k == "event:e1:registration:r1:message:warmup-media:v1:slot:a-b:message-revision:2:asset-revision:3"
    assert es.followup_media_dispatch_key(event_id="e1", registration_id="r1", stage=1, slot_key="p", message_revision=1,
                                          asset_revision=1).startswith("event:e1:registration:r1:message:post-media:v1:stage:1")
    st = _st()
    ok, facts = es.materialize_media(st, key=k, registration_id="r1", platform="telegram", connection_id="c",
                                     recipient_kind="external_subject", external_subject="42", asset_kind="image",
                                     asset_reference="/m/a.png")
    assert ok and facts[0]["step"] == "event_media_queued"
    again, none = es.materialize_media(_st(*facts), key=k, registration_id="r1", platform="telegram", connection_id="c",
                                       recipient_kind="external_subject", external_subject="42", asset_kind="image",
                                       asset_reference="/m/a.png")
    assert again is False and none == []


def test_email_target_needs_active_connection_and_subjects_are_per_segment() -> None:
    from application.business_flows import native_channels as nc

    conn, pending = nc.provision_email_smtp(sender_email="o@example.ru", smtp_host="smtp.example.ru", smtp_port=465,
                                            username_ref="env:U", password_ref="env:P")
    conns = nc.email_replay(pending)
    assert es.resolve_email_target(conns, email_connection_id=conn.id, email="a@x.ru") is None  # still pending
    _, active = nc.verify_and_activate_email_smtp(conns, conn.id, lambda c: None)
    target = es.resolve_email_target(nc.email_replay(pending + active), email_connection_id=conn.id, email="a@x.ru")
    assert target["platform"] == "email" and target["external_subject"] == "a@x.ru"
    assert es.resolve_email_target({}, email_connection_id="nope", email="a@x.ru") is None
    assert es.followup_subject("no_show", title="Йога") == "Вы регистрировались: Йога"
    with pytest.raises(ValueError):
        es.followup_subject("other", title="x")


def test_prepare_stage_visual_text_only_stage_has_no_receipt_and_visual_stage_is_deterministic() -> None:
    from application.business_flows import visual_creatives as vcr

    gens = vcr.gen_replay([])
    kw = dict(business_id="b1", brand_facts=[], event_id="e1", stage="warmup", message_key="w1", event_title="Йога",
              message_text="Приходите на йогу", now_ms=NOW)
    assert es.prepare_stage_visual(_st(), gens, "u1", **kw) == (None, [])
    st = _st(es.set_content_mode("e1", "warmup", "text_with_image"))
    res, facts = es.prepare_stage_visual(st, gens, "u1", **kw)
    assert res["mode"] == "text_with_image" and facts[-1]["step"] == "gen_prepared"
    assert res["idempotency_key"] == "event:e1:warmup:w1:image:v1"
    binding = vcr.frozen_binding(facts[-1]["provider_payload_json"])
    assert binding == {"type": "event_content", "event_id": "e1", "stage": "warmup", "slot_key": "w1", "kind": "image"}
    res2, facts2 = es.prepare_stage_visual(st, vcr.gen_replay(facts), "u1", **kw)
    assert facts2 == [] and res2["receipt_id"] == res["receipt_id"]  # idempotent
