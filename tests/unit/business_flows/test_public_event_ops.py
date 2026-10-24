from __future__ import annotations

from functools import partial
from types import SimpleNamespace

import pytest

from contracts.customer import CustomerIdentityConflict
from runtime._internal.effects_domains.crm_projection import CrmProjectionEffectsMixin
from runtime.handler_impl.domains.business_flow_ops import handle_event_series

NOW = 1_800_000_000_000  # 2027-01-15


def _run(flow, op, arg):
    return flow.run(partial(handle_event_series, now_ms=NOW), op=op, arg=arg)[1]


def _slug(flow):
    return next(e["payload"]["slug"] for e in flow.store.events if e["payload"].get("step") == "pub_event_created")


def test_register_bind_links_verify(flow) -> None:
    calls = []

    def crm(**kw):
        calls.append(kw)
        return {"ok": True, "customer_id": "cus_1"}

    flow.effects.ensure_customer_identity = crm
    assert "Опубликовано" in _run(flow, "pub_create", "Вебинар | 2027-02-01 19:00 | Europe/Moscow")
    slug = _slug(flow)
    assert "Клиент привязан" in _run(flow, "pub_register", f"{slug} | Анна | anna@example.com")
    assert calls[0]["channel"] == "email" and calls[0]["decision_id"] == "d"
    assert "уже зарегистрированы" in _run(flow, "pub_register", f"{slug} | Анна | anna@example.com")
    text = _run(flow, "pub_links", slug)
    token = text.split("/event_verify ")[1].split()[0]
    assert "напоминания" in _run(flow, "pub_verify", token)
    assert "Ошибка" in _run(flow, "pub_verify", token) or "⚠" in _run(flow, "pub_verify", token)


def test_crm_unavailable_keeps_registration_and_blocks_links(flow) -> None:
    flow.effects.ensure_customer_identity = lambda **kw: {"ok": False, "reason": "crm_unavailable"}
    _run(flow, "pub_create", "Вебинар | 2027-02-01 19:00 | Europe/Moscow")
    slug = _slug(flow)
    assert "crm_unavailable" in _run(flow, "pub_register", f"{slug} | Анна | anna@example.com")
    assert any(e["payload"].get("step") == "pub_registration" for e in flow.store.events)
    assert "привязанной" in _run(flow, "pub_links", slug)


class _Log:
    def __init__(self):
        self.ev = []

    def emit(self, **kw):
        self.ev.append(kw)


class _Fx(CrmProjectionEffectsMixin):
    def __init__(self, reg):
        self.event_log, self.customer_registry = _Log(), reg


def _call(fx, **kw):
    return fx.ensure_customer_identity(decision_id="d", correlation_id="c", tenant_id="t", business_id="b",
                                       channel=kw.pop("channel", "email"), external_subject="a@x.ru", **kw)


def test_effect_requires_executor_and_handles_registry(monkeypatch) -> None:
    import runtime._internal.effects_domains.crm_projection as m
    monkeypatch.setattr(m, "assert_called_from_executor", lambda: None)
    assert _call(_Fx(None)) == {"ok": False, "reason": "crm_unavailable"}
    reg = SimpleNamespace(ensure_customer_identity=lambda **kw: SimpleNamespace(customer=SimpleNamespace(customer_id="c9")))
    fx = _Fx(reg)
    assert _call(fx) == {"ok": True, "customer_id": "c9"} and fx.event_log.ev[0]["event_type"] == "crm_identity_projected"

    def conflict(**kw):
        raise CustomerIdentityConflict("x")
    assert _call(_Fx(SimpleNamespace(attach_identity=conflict)), customer_id="c9")["reason"] == "identity_conflict"
    with pytest.raises(ValueError):
        _call(fx, channel="telegram")


def test_effect_blocked_outside_executor() -> None:
    with pytest.raises(Exception):
        _call(_Fx(None))


def test_ad_creatives_advisory_text() -> None:
    from runtime.handler_impl.domains.business_catalog_ops import _creatives_text

    text = _creatives_text("bookings ; A:j1:5000:200:60:10 ; B:j2:5000:200:10:2")
    assert "ready" in text and "Лидер: A" in text and "A 50%→60%" in text and "бюджет не меняется" in text
    assert "insufficient_data" in _creatives_text("A:j1:5000:5:1:0 ; B:j2:5000:5:1:0")
    with pytest.raises(ValueError):
        _creatives_text("A:j1")


def test_event_live_snapshot_lists_session_rooms(flow) -> None:
    from application.business_flows import event_owner_flow as eo

    _run(flow, "pub_create", "Вебинар | 2027-02-01 19:00 | Europe/Moscow")
    slug = _slug(flow)
    text = _run(flow, "pub_live", slug)
    assert "Вебинар" in text and "01.02.2027 19:00" in text and "ссылка не задана" in text
    payloads = [e["payload"] for e in flow.store.events]
    ev_id = payloads[0]["event_id"]
    two = [{"starts_at": "2027-02-01T16:00:00+00:00", "join_url": "https://telemost.yandex.ru/j/1",
            "provider_key": "telemost"},
           {"starts_at": "2027-02-02T16:00:00+00:00", "join_url": None}]
    snap = eo.live_snapshot([*payloads, {"step": "pub_event_sessions", "event_id": ev_id, "sessions": two}], slug)
    assert [s["join_ready"] for s in snap["sessions"]] == [True, False]
    assert snap["sessions"][1]["local_start"] == "02.02.2027 19:00" and snap["sessions"][1]["provider_key"] == "pending"


# ---- photo / e-mail / visual-asset ops (media_op): facts only, sends are flagged executor effects ----
def _facts(flow, step):
    return [e["payload"] for e in flow.store.events if e["payload"].get("step") == step]


def test_asset_set_show_replace_queues_cleanup(flow) -> None:
    assert "Визуал сохранён (ревизия 1)" in _run(flow, "asset_set", "e1 | warmup | k1 | image | /m/a.png")
    assert "ревизия 1" in _run(flow, "asset_show", "e1 | warmup | k1")
    assert "ревизия 2" in _run(flow, "asset_set", "e1 | warmup | k1 | image | /m/b.png")
    assert _facts(flow, "batch")[0]["facts"][1] == {"step": "media_cleanup_queued", "reference": "/m/a.png",
                                                    "reason": "superseded_event_content_asset"}
    assert "ревизия 2" in _run(flow, "asset_show", "e1 | warmup | k1")  # batch facts replay
    assert "Не получилось" in _run(flow, "asset_set", "e1 | nope | k1 | image | /m/a.png")
    assert "Не получилось" in _run(flow, "asset_set", "e1 | warmup | k1 | gif | /m/a.png")


def test_asset_send_is_dry_run_without_flag_and_executor_call_with_flag(flow, monkeypatch) -> None:
    calls = []
    flow.effects.send_photo = lambda **kw: calls.append(kw) or {"ok": True, "status": "dry_run"}
    _run(flow, "asset_set", "e1 | warmup | k1 | image | /m/a.png")
    assert "ничего не ушло" in _run(flow, "asset_send", "e1 | warmup | k1")
    assert calls[0]["path"] == "/m/a.png" and calls[0]["user_id"] == "u1" and calls[0]["decision_id"] == "d"
    flow.effects.send_photo = lambda **kw: {"ok": True, "status": "sent"}
    assert "отправлено" in _run(flow, "asset_send", "e1 | warmup | k1")
    flow.effects.send_photo = lambda **kw: {"ok": False, "reason": "TELEGRAM_BOT_TOKEN_MISSING"}
    assert "не отправлено" in _run(flow, "asset_send", "e1 | warmup | k1")
    assert "Не получилось" in _run(flow, "asset_send", "e1 | warmup | nokey")
    _run(flow, "asset_set", "e1 | warmup | kv | video | /m/v.mp4")
    assert "Видео не отправляется" in _run(flow, "asset_send", "e1 | warmup | kv")


def test_asset_send_without_photo_effect_is_closed(flow) -> None:
    _run(flow, "asset_set", "e1 | warmup | k1 | image | /m/a.png")
    assert "недоступна" in _run(flow, "asset_send", "e1 | warmup | k1")


def test_stage_visual_prepares_one_receipt_and_gen_lifecycle(flow) -> None:
    assert "только текст" in _run(flow, "stage_visual", "e1 | warmup | m1 | Вебинар | Приходите на вебинар")
    assert "видео недоступно" in _run(flow, "content_mode", "e1 | warmup | text_with_video")
    assert "Не получилось" in _run(flow, "content_mode", "e1 | bad | text_with_image")
    assert "text_with_image" in _run(flow, "content_mode", "e1 | warmup | text_with_image")
    out = _run(flow, "stage_visual", "e1 | warmup | m1 | Вебинар | Приходите на вебинар")
    assert "НЕ запускалась" in out
    rid = out.split("Заявка ")[1].split()[0]
    assert rid in _run(flow, "gen", "show")
    _run(flow, "stage_visual", "e1 | warmup | m1 | Вебинар | Приходите на вебинар")  # identical request: idempotent
    assert len(_facts(flow, "gen_prepared")) == 1
    assert "Без изменений" in _run(flow, "gen", f"abandon {rid}")  # only a finished result can be discarded
    calls = []
    flow.effects.generate_visual_creative = lambda **kw: calls.append(kw) or {"ok": True, "job": {"id": "job_1", "status": "succeeded"}}
    assert "job_1" in _run(flow, "gen", f"submit {rid}")
    assert calls[0]["kind"] == "image" and calls[0]["decision_id"] == "d" and len(calls) == 1
    assert "повторная отправка не делается" in _run(flow, "gen", f"submit {rid}") and len(calls) == 1
    assert "succeeded" in _run(flow, "gen", "show")
    assert "Готово" in _run(flow, "gen", f"abandon {rid}")
    assert "Активной заявки на изображение нет" in _run(flow, "gen", "show")
    assert "Не получилось" in _run(flow, "gen", "frobnicate " + rid)


def test_email_connection_flag_gates_probe_and_send(flow, monkeypatch) -> None:
    out = _run(flow, "email_connect", "Owner@Example.ru | smtp.example.ru | 465 | env:SMTP_USER | env:SMTP_PASS | ssl")
    cid = out.split("Подключение ")[1].split()[0]
    assert "ожидает проверки" in out and "env:SMTP_PASS" in str(flow.store.events)  # only the reference is stored
    assert "Не получилось" in _run(flow, "email_connect", "a@b.ru | h | 465 | plain-user | plain-pass")  # raw secrets refused
    monkeypatch.delenv("BAI_EMAIL_EFFECTS_ENABLED", raising=False)
    probes = []
    flow.effects.email_smtp_probe = lambda **kw: probes.append(kw) or {"ok": True}
    assert "выключена" in _run(flow, "email_verify", cid) and probes == []
    monkeypatch.setenv("BAI_EMAIL_EFFECTS_ENABLED", "1")
    assert "активно" in _run(flow, "email_verify", cid) and probes[0]["connection_id"] == cid
    assert _facts(flow, "email_conn_active")
    # sending: flag off -> only a dry-run fact; flag on -> executor send_message(channel="email")
    monkeypatch.delenv("BAI_EMAIL_EFFECTS_ENABLED")
    before = len(flow.effects.sent)
    assert "записано, но не отправлено" in _run(flow, "email_test", f"{cid} | a@x.ru | Тема | Текст")
    assert all(s.get("channel") != "email" for s in flow.effects.sent[before:])
    assert _facts(flow, "email_dry_run")[0]["to"] == "a@x.ru"
    monkeypatch.setenv("BAI_EMAIL_EFFECTS_ENABLED", "1")
    assert "передано исполнителю" in _run(flow, "email_test", f"{cid} | a@x.ru | Тема | Текст")
    mail = [s for s in flow.effects.sent if s.get("channel") == "email"]
    assert mail[0]["subject"] == "Тема" and mail[0]["user_id"] == "a@x.ru"
    assert _facts(flow, "email_sent")


def test_email_probe_rejection_keeps_connection_pending(flow, monkeypatch) -> None:
    out = _run(flow, "email_connect", "o@example.ru | smtp.example.ru | 587 | env:U | vault:P | starttls")
    cid = out.split("Подключение ")[1].split()[0]
    monkeypatch.setenv("BAI_EMAIL_EFFECTS_ENABLED", "1")
    flow.effects.email_smtp_probe = lambda **kw: {"ok": False}
    assert "Не получилось" in _run(flow, "email_verify", cid)
    assert not _facts(flow, "email_conn_active")
    assert "Не получилось" in _run(flow, "email_test", f"{cid} | a@x.ru | T | X")  # pending: no sending


def test_adproject_lifecycle_and_render_expiry(flow) -> None:
    from application.business_flows import ad_proposals as ap

    flow.effects.send_message(tenant_id="t1", user_id="u1", text="x", track_event_type="business_admin@v1",
                              track_payload=ap.draft("Заголовок | Текст | https://x.ru"))
    draft_id = _facts_any(flow, "ad_drafted")["draft_id"]
    out = _run(flow, "adproject", f"create {draft_id} | image | Скидка | Только сегодня")
    pid = out.split("Проект ")[1].split(":")[0]
    assert "r1" in out
    assert "r2" in _run(flow, "adproject", f"edit {pid} | Новая скидка")
    assert pid in _run(flow, "adproject", f"show {pid}")
    assert "Не получилось" in _run(flow, "adproject", "create nodraft | image | A | B")
    assert "Не получилось" in _run(flow, "adproject", f"render {pid}")  # no source bound yet
    _run(flow, "adproject", f"bind {pid} | job1")
    flow.effects.poll_visual_creative = lambda **kw: {"status": "succeeded", "asset_ready": False, "kind": "image"}
    assert "устарел" in _run(flow, "adproject", f"render {pid}")
    assert any(f.get("step") == "eap_set" for f in _facts(flow, "batch") + _facts(flow, "eap_set"))
    assert "source_expired" in _run(flow, "adproject", f"show {pid}")
    flow.effects.poll_visual_creative = lambda **kw: {"status": "succeeded", "asset_ready": True, "kind": "image"}
    assert "Не получилось" in _run(flow, "adproject", f"render {pid}")  # expired source cannot render
    assert "r" in _run(flow, "adproject", f"new_source {pid}")


def _facts_any(flow, step):
    return next(e["payload"] for e in flow.store.events if e["payload"].get("step") == step)


def test_gen_submit_unconfirmed_gateway_blocks_blind_resubmit(flow) -> None:
    _run(flow, "content_mode", "e1 | warmup | text_with_image")
    rid = _run(flow, "stage_visual", "e1 | warmup | m1 | Вебинар | Текст").split("Заявка ")[1].split()[0]

    def boom(**kw):
        raise TimeoutError("gateway timeout")

    flow.effects.generate_visual_creative = boom
    assert "повтор запрещён" in _run(flow, "gen", f"submit {rid}")
    flow.effects.generate_visual_creative = lambda **kw: pytest.fail("must not resubmit after an unknown outcome")
    assert "повторная отправка не делается" in _run(flow, "gen", f"submit {rid}")


def test_visual_style_clear_via_command(flow) -> None:
    assert "не был задан" in _run(flow, "visual", "Вебинар | style | clear")
    _run(flow, "visual", "Вебинар | style | minimal")
    assert "сброшен" in _run(flow, "visual", "Вебинар | style | clear")
    assert "не был задан" in _run(flow, "visual", "Вебинар | style | clear")
