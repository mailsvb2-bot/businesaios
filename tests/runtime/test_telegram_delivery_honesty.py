from __future__ import annotations

from runtime._internal.effects_actions.telegram.messaging_parts.transport import telegram_delivery
from runtime.messaging.outbound_message import OutboundMessage
from runtime.platform.delivery_state import DeliveryState


class _DummyEventLog:
    def emit(self, **kwargs):
        return None


class _QueuedSelf:
    def __init__(self, state):
        self.delivery_state = state
        self.event_log = _DummyEventLog()
        self.telegram_outbound_queue = object()
        self._last_sent = {}

    def _telegram_send_message(self, **kwargs):
        return True, {'mode': 'queued', 'channel': 'telegram'}


class _DirectSelf:
    def __init__(self, state):
        self.delivery_state = state
        self.event_log = _DummyEventLog()
        self.telegram_outbound_queue = None
        self._last_sent = {}

    def _telegram_send_message(self, **kwargs):
        return True, {'mode': 'direct', 'channel': 'telegram', 'external_id': '555'}


def test_queued_transport_does_not_mark_delivery_finalized(tmp_path) -> None:
    state = DeliveryState(db_path=tmp_path / 'queued.sqlite')
    owner = _QueuedSelf(state)
    msg = OutboundMessage(decision_id='d1', correlation_id='c1', tenant_id='t1', user_id='42', channel='telegram', text='hello')

    ok, meta = telegram_delivery(owner, msg=msg)

    assert ok is True
    assert meta['mode'] == 'queued'
    assert meta['delivery_finalized'] is False
    assert state.is_delivered(msg.delivery_key) is False


def test_direct_transport_marks_delivery_finalized(tmp_path) -> None:
    state = DeliveryState(db_path=tmp_path / 'direct.sqlite')
    owner = _DirectSelf(state)
    msg = OutboundMessage(decision_id='d1', correlation_id='c1', tenant_id='t1', user_id='42', channel='telegram', text='hello')

    ok, meta = telegram_delivery(owner, msg=msg)

    assert ok is True
    assert meta['delivery_finalized'] is True
    assert state.is_delivered(msg.delivery_key) is True
    receipt = state.get_receipt(msg.delivery_key)
    assert receipt is not None
    assert receipt['external_id'] == '555'


# ---- photo delivery: executor-only, off by default, fakes only ----
import pytest  # noqa: E402

from runtime._internal.effects_actions.telegram import media as _media  # noqa: E402
from runtime._internal.effects_clients import telegram_client as _tc  # noqa: E402


class _PhotoLog:
    def __init__(self):
        self.ev = []

    def emit(self, **kw):
        self.ev.append(kw)


def _photo_fx(monkeypatch):
    monkeypatch.setattr(_media, "assert_called_from_executor", lambda: None)
    monkeypatch.setattr(_media, "assert_event_log_tenant", lambda log, tenant_id, operation: tenant_id)
    return type("Fx", (), {"event_log": _PhotoLog()})()


def _photo(fx, **kw):
    return _media.send_photo_effect(fx, decision_id="d", correlation_id="c", tenant_id="t1", user_id="42",
                                    path="/tmp/x.png", **kw)


def test_photo_flag_is_off_by_default_and_dry_run_has_no_network(monkeypatch) -> None:
    monkeypatch.delenv(_media.PHOTO_DELIVERY_ENV, raising=False)
    fx = _photo_fx(monkeypatch)
    monkeypatch.setattr(_media, "telegram_send_photo_transport",
                        lambda *a, **k: pytest.fail("network transport must not run while the flag is off"))
    out = _photo(fx)
    assert out["ok"] is True and out["status"] == "dry_run"
    assert [e["event_type"] for e in fx.event_log.ev] == ["photo_dry_run"]


def test_photo_flag_on_uses_transport_and_records(monkeypatch) -> None:
    monkeypatch.setenv(_media.PHOTO_DELIVERY_ENV, "1")
    fx = _photo_fx(monkeypatch)
    seen = {}

    def fake_transport(effects, **kw):
        seen.update(kw)
        return True, {"mode": "fake", "delivery_finalized": True}

    monkeypatch.setattr(_media, "telegram_send_photo_transport", fake_transport)
    out = _photo(fx, caption="hi")
    assert out["ok"] is True and out.get("status") != "dry_run"
    assert seen["chat_id"] == "42" and seen["photo_url"] == "/tmp/x.png" and seen["caption"] == "hi"
    assert [e["event_type"] for e in fx.event_log.ev] == ["photo_sent"]


def test_photo_unsupported_channel_is_refused(monkeypatch) -> None:
    monkeypatch.setenv(_media.PHOTO_DELIVERY_ENV, "1")
    fx = _photo_fx(monkeypatch)
    out = _photo(fx, channel="email")
    assert out["ok"] is False and "UNSUPPORTED_PHOTO_CHANNEL" in str(out)


def test_client_send_photo_without_token_fails_closed_and_dedups(monkeypatch, tmp_path) -> None:
    client = _tc.TelegramClient(transport=object(), delivery_state=DeliveryState(db_path=tmp_path / "p.sqlite"))
    monkeypatch.setattr(_tc, "_token", lambda: "")
    ok, meta = client.send_photo(chat_id="42", photo_url="https://x/y.png", caption=" cap ")
    assert ok is False and meta["error"] == "TELEGRAM_BOT_TOKEN_MISSING" and meta["delivery_finalized"] is False
    monkeypatch.setattr(_tc, "_token", lambda: "TEST")
    calls = []
    monkeypatch.setattr(client, "_http_post", lambda **kw: calls.append(kw) or {"ok": True, "result": {"message_id": 7}})
    ok, meta = client.send_photo(chat_id="42", photo_url="https://x/y.png", caption="cap")
    assert ok is True and meta["external_id"] == "7" and len(calls) == 1
    ok2, meta2 = client.send_photo(chat_id="42", photo_url="https://x/y.png", caption="cap")
    assert ok2 is True and meta2["mode"] == "dedup" and len(calls) == 1


def test_client_send_photo_uploads_local_file_and_never_raises(monkeypatch, tmp_path) -> None:
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG")
    client = _tc.TelegramClient(transport=object(), delivery_state=DeliveryState(db_path=tmp_path / "p.sqlite"))
    monkeypatch.setattr(_tc, "_token", lambda: "TEST")
    seen = {}
    monkeypatch.setattr(_tc, "http_multipart_file", lambda url, **kw: seen.update(kw) or {"ok": True, "result": {"message_id": 1}})
    ok, _ = client.send_photo(chat_id="9", photo_url=str(img))
    assert ok is True and seen["field_name"] == "photo" and seen["path"] == str(img)

    def boom(url, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(_tc, "http_multipart_file", boom)
    img2 = tmp_path / "b.png"
    img2.write_bytes(b"\x89PNG2")
    ok, meta = client.send_photo(chat_id="9", photo_url=str(img2))
    assert ok is False and "network down" in meta["error"]
