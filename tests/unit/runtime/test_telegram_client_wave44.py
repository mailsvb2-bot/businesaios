from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

import runtime._internal.effects_clients.telegram_client as sut


class Queue:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def enqueue(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class LimitedQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, *, method, chat_id):
        self.calls.append((method, chat_id))
        return None


@pytest.fixture
def env(monkeypatch):
    values = {
        "TELEGRAM_API_BASE": " https://telegram.invalid/ ",
        "TELEGRAM_BOT_TOKEN": " token ",
        "APP_ENV": "dev",
        "ENV": "dev",
    }
    monkeypatch.setattr(sut, "env_str", lambda name, default="": values.get(name, default))
    monkeypatch.setattr(sut, "env_bool", lambda name, default=False: bool(values.get(name, default)))
    return values


def client(*, queue=None, state=None):
    return sut.TelegramClient(outbound_queue=queue, transport="transport", delivery_state=state)


def test_environment_wrappers_and_transport_initialization(monkeypatch, env):
    assert sut.telegram_api_base() == "https://telegram.invalid"
    assert sut._token() == "token"
    assert sut._strict_token_required() is False
    env["APP_ENV"] = "production"
    assert sut._strict_token_required() is True
    env["APP_ENV"] = "dev"
    env["TELEGRAM_STRICT_TOKEN"] = True
    assert sut._strict_token_required() is True

    monkeypatch.setattr(sut, "stable_json", lambda payload: "json")
    monkeypatch.setattr(sut, "build_payload_digest", lambda payload: "digest")
    monkeypatch.setattr(sut, "build_delivery_key", lambda **kwargs: "key")
    assert sut._stable_json({"a": 1}) == "json"
    assert sut._payload_digest({"a": 1}) == "digest"
    assert sut._delivery_key(method="send", chat_id="1", payload={}) == "key"

    transport = object()
    factory = Mock(return_value=transport)
    monkeypatch.setattr(sut, "build_http_transport", factory)
    created = sut.TelegramClient()
    assert created.transport is transport
    factory.assert_called_once_with()
    explicit = sut.TelegramClient(transport="given")
    assert explicit.transport == "given"


def test_get_me_and_webhook_contracts(monkeypatch, env):
    http = Mock(return_value={"ok": True})
    monkeypatch.setattr(sut, "http_json", http)
    c = client()
    assert c.get_me(token=" explicit ", timeout_s=0) == {"ok": True}
    assert http.call_args.args[:3] == (
        "GET",
        "https://telegram.invalid/botexplicit/getMe",
        None,
    )
    assert http.call_args.kwargs["timeout_s"] == 20
    assert c.get_webhook_info(timeout_s=7) == {"ok": True}
    assert http.call_args.args[1].endswith("/bottoken/getWebhookInfo")
    assert http.call_args.kwargs["timeout_s"] == 7

    env["TELEGRAM_BOT_TOKEN"] = ""
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN_MISSING"):
        c.get_me()
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN_MISSING"):
        c.get_webhook_info()


def test_answer_callback_query_paths(monkeypatch, env):
    c = client()
    enqueue = Mock(return_value=True)
    post = Mock()
    monkeypatch.setattr(c, "_enqueue_transport", enqueue)
    monkeypatch.setattr(c, "_http_post", post)
    c.answer_callback_query("cb", text=" hi ", show_alert=True)
    payload = enqueue.call_args.kwargs["payload"]
    assert payload["text"] == "hi"
    assert payload["show_alert"] is True
    post.assert_not_called()

    enqueue.reset_mock()
    enqueue.return_value = False
    c.answer_callback_query("cb", text=" ", show_alert=False)
    assert "text" not in enqueue.call_args.kwargs["payload"]
    post.assert_called_once()

    swallowed = Mock()
    monkeypatch.setattr(sut, "swallow", swallowed)
    enqueue.side_effect = RuntimeError("queue")
    post.reset_mock()
    c.answer_callback_query("cb")
    swallowed.assert_called_once()
    post.assert_called_once()

    post.side_effect = RuntimeError("http")
    c.answer_callback_query("cb")
    env["TELEGRAM_BOT_TOKEN"] = ""
    enqueue.reset_mock()
    c.answer_callback_query("cb")
    enqueue.assert_not_called()


def test_send_chat_action_paths(monkeypatch, env):
    c = client()
    enqueue = Mock(return_value=True)
    post = Mock()
    monkeypatch.setattr(c, "_enqueue_transport", enqueue)
    monkeypatch.setattr(c, "_http_post", post)
    c.send_chat_action(chat_id="7", action="")
    assert enqueue.call_args.kwargs["payload"]["action"] == "typing"
    post.assert_not_called()

    enqueue.return_value = False
    c.send_chat_action(chat_id="7", action="upload_audio")
    post.assert_called_once()

    swallowed = Mock()
    monkeypatch.setattr(sut, "swallow", swallowed)
    enqueue.side_effect = RuntimeError("queue")
    post.reset_mock()
    c.send_chat_action(chat_id="7")
    swallowed.assert_called_once()
    post.assert_called_once()
    post.side_effect = RuntimeError("http")
    c.send_chat_action(chat_id="7")

    env["TELEGRAM_BOT_TOKEN"] = ""
    enqueue.reset_mock()
    c.send_chat_action(chat_id="7")
    enqueue.assert_not_called()


def test_recovery_wrapper_and_existing_receipt_requeue(monkeypatch):
    recover_all = Mock(return_value=[{"key": "one"}])
    monkeypatch.setattr(sut, "recover_inflight_receipts", recover_all)
    c = client(state="state")
    assert c.recover_inflight_accepted_receipts(stale_after_ms=10, limit=2) == [
        {"key": "one"}
    ]
    recover_all.assert_called_once_with("state", stale_after_ms=10, limit=2)

    kwargs = dict(
        existing={"phase": "accepted"},
        method="sendMessage",
        chat_id="1",
        payload={"chat_id": "1"},
        priority="normal",
        critical=True,
        timeout_s=30,
        url="url",
        delivery_key="key",
        payload_digest="digest",
    )
    assert c._maybe_requeue_existing_receipt(**{**kwargs, "existing": None}) is None
    c.outbound_queue = None
    assert c._maybe_requeue_existing_receipt(**kwargs) is None
    c.outbound_queue = object()
    monkeypatch.setattr(sut, "accepted_receipt_stale", lambda existing: False)
    assert c._maybe_requeue_existing_receipt(**kwargs) is None

    monkeypatch.setattr(sut, "accepted_receipt_stale", lambda existing: True)
    monkeypatch.setattr(sut, "delivery_metadata", lambda **values: dict(values))
    monkeypatch.setattr(sut, "receipt_phase", lambda *args, **kwargs: "accepted")
    enqueue = Mock(return_value=False)
    monkeypatch.setattr(c, "_enqueue_transport", enqueue)
    assert c._maybe_requeue_existing_receipt(**kwargs) is None

    enqueue.return_value = True
    recovered = Mock(return_value={"phase": "recovery"})
    monkeypatch.setattr(sut, "recover_stale_receipt", recovered)
    assert c._maybe_requeue_existing_receipt(**kwargs) == {"phase": "recovery"}
    recovered.return_value = None
    assert c._maybe_requeue_existing_receipt(**kwargs) == kwargs["existing"]


def test_http_and_queue_callable_delivery_paths(monkeypatch):
    c = client(state="state")
    http = Mock(return_value={"ok": True, "result": {"message_id": 9}})
    monkeypatch.setattr(sut, "http_json", http)
    assert c._http_post(url="u", payload={"x": 1}, timeout_s=0)["ok"] is True
    assert http.call_args.kwargs["timeout_s"] == 30

    delivered = Mock()
    monkeypatch.setattr(sut, "mark_transport_delivered", delivered)
    monkeypatch.setattr(c, "_http_post", Mock(return_value={"ok": True, "result": {"message_id": 7}}))
    run = c._queue_callable(
        url="u",
        payload={"x": 1},
        timeout_s=3,
        delivery_key="key",
        payload_digest="digest",
        delivered_metadata={"mode": "worker"},
    )
    assert run()["ok"] is True
    assert delivered.call_args.kwargs["external_id"] == "7"

    delivered.reset_mock()
    c._http_post.return_value = {"ok": False}
    assert c._queue_callable(
        url="u", payload={}, timeout_s=1, delivery_key="key", payload_digest="digest"
    )() == {"ok": False}
    delivered.assert_not_called()
    c._http_post.return_value = "not-a-dict"
    assert c._queue_callable(url="u", payload={}, timeout_s=1)() == {}


def test_enqueue_transport_adapts_queue_signatures_and_failures():
    c = client(queue=None)
    assert c._enqueue_transport(
        method="send", chat_id="1", payload={}, priority="p", critical=False, meta={}, fn=lambda: None
    ) is False
    c.outbound_queue = object()
    assert c._enqueue_transport(
        method="send", chat_id="1", payload={}, priority="p", critical=False, meta={}, fn=lambda: None
    ) is False

    c.outbound_queue = Queue([None])
    assert c._enqueue_transport(
        method="send", chat_id="12", payload={"x": 1}, priority="p", critical=True, meta={}, fn=lambda: None
    ) is True
    assert c.outbound_queue.calls[0]["chat_id"] == 12

    c.outbound_queue = Queue([False])
    assert c._enqueue_transport(
        method="send", chat_id="not-number", payload={}, priority="p", critical=False, meta={}, fn=lambda: None
    ) is False
    assert c.outbound_queue.calls[0]["chat_id"] is None

    c.outbound_queue = Queue([TypeError(), TypeError(), True])
    assert c._enqueue_transport(
        method="send", chat_id=None, payload={}, priority="p", critical=False, meta={}, fn=lambda: None
    ) is True

    c.outbound_queue = LimitedQueue()
    assert c._enqueue_transport(
        method="send", chat_id="3", payload={}, priority="p", critical=False, meta={}, fn=lambda: None
    ) is True
    assert c.outbound_queue.calls == [("send", 3)]

    c.outbound_queue = Queue([RuntimeError("queue")])
    with pytest.raises(RuntimeError, match="queue"):
        c._enqueue_transport(
            method="send", chat_id="1", payload={}, priority="p", critical=False, meta={}, fn=lambda: None
        )

    class BrokenSignature:
        @property
        def enqueue(self):
            return Mock(side_effect=TypeError())

    c.outbound_queue = BrokenSignature()
    assert c._enqueue_transport(
        method="send", chat_id="1", payload={}, priority="p", critical=False, meta={}, fn=lambda: None
    ) is False


def install_delivery_fakes(monkeypatch, *, token="token", existing=None, strict=False):
    monkeypatch.setattr(sut, "_token", lambda: token)
    monkeypatch.setattr(sut, "_strict_token_required", lambda: strict)
    monkeypatch.setattr(sut, "telegram_api_base", lambda: "https://api")
    monkeypatch.setattr(sut, "_payload_digest", lambda payload: "digest")
    monkeypatch.setattr(sut, "_delivery_key", lambda **kwargs: "key")
    monkeypatch.setattr(sut, "existing_receipt", Mock(return_value=existing))
    monkeypatch.setattr(sut, "receipt_phase", lambda value, default=None: (value or {}).get("phase", default))
    monkeypatch.setattr(sut, "delivery_metadata", lambda **kwargs: dict(kwargs))
    monkeypatch.setattr(sut, "mark_transport_accepted", Mock())
    monkeypatch.setattr(sut, "mark_transport_delivered", Mock())
    monkeypatch.setattr(sut, "recover_stale_receipt", Mock())


@pytest.mark.parametrize("method", ["send_message", "send_audio"])
def test_delivery_existing_receipt_dedup_and_recovery(monkeypatch, method):
    install_delivery_fakes(monkeypatch, existing={"phase": "finalized", "external_id": "9"})
    c = client()
    monkeypatch.setattr(c, "_maybe_requeue_existing_receipt", Mock(return_value=None))
    call = getattr(c, method)
    kwargs = {"chat_id": "1", "text": "hello"} if method == "send_message" else {"chat_id": "1", "audio_url": "audio"}
    ok, meta = call(**kwargs)
    assert ok is True and meta["mode"] == "dedup" and meta["delivery_finalized"] is True

    c._maybe_requeue_existing_receipt.return_value = {"phase": "recovery"}
    ok, meta = call(**kwargs)
    assert ok is True and meta["mode"] == "queued_recovery"


@pytest.mark.parametrize("method", ["send_message", "send_audio"])
def test_delivery_missing_token_strict_and_noop(monkeypatch, method):
    call_kwargs = {"chat_id": "1", "text": "hello"} if method == "send_message" else {"chat_id": "1", "audio_url": "audio", "caption": " cap "}
    install_delivery_fakes(monkeypatch, token="", strict=True)
    ok, meta = getattr(client(), method)(**call_kwargs)
    assert ok is False and meta["error"] == "TELEGRAM_BOT_TOKEN_MISSING"
    install_delivery_fakes(monkeypatch, token="", strict=False)
    ok, meta = getattr(client(), method)(**call_kwargs)
    assert ok is True and meta["mode"] == "noop"


@pytest.mark.parametrize("method", ["send_message", "send_audio"])
def test_delivery_queue_success_and_fallback(monkeypatch, method):
    install_delivery_fakes(monkeypatch)
    c = client(queue=object())
    enqueue = Mock(return_value=True)
    monkeypatch.setattr(c, "_enqueue_transport", enqueue)
    kwargs = {"chat_id": "1", "text": "hello", "reply_markup": {"a": 1}} if method == "send_message" else {"chat_id": "1", "audio_url": "audio", "caption": " cap "}
    ok, meta = getattr(c, method)(**kwargs)
    assert ok is True and meta["mode"] == "queued"
    assert enqueue.call_args.kwargs["payload"]["chat_id"] == "1"

    enqueue.return_value = False
    monkeypatch.setattr(c, "_http_post", Mock(return_value={"ok": True, "result": {"message_id": 5}}))
    ok, meta = getattr(c, method)(**kwargs)
    assert ok is True and meta["mode"] == "direct" and meta["external_id"] == "5"

    swallowed = Mock()
    monkeypatch.setattr(sut, "swallow", swallowed)
    enqueue.side_effect = RuntimeError("queue")
    ok, meta = getattr(c, method)(**kwargs)
    assert ok is True and meta["mode"] == "direct"
    swallowed.assert_called()


@pytest.mark.parametrize("method", ["send_message", "send_audio"])
def test_delivery_direct_false_non_mapping_and_exception(monkeypatch, method):
    install_delivery_fakes(monkeypatch)
    c = client()
    kwargs = {"chat_id": "1", "text": "hello", "reply_markup": "bad"} if method == "send_message" else {"chat_id": "1", "audio_url": "audio", "caption": " "}
    post = Mock(return_value={"ok": False, "result": "none"})
    monkeypatch.setattr(c, "_http_post", post)
    ok, meta = getattr(c, method)(**kwargs)
    assert ok is False and meta["external_id"] is None

    post.return_value = "not-a-dict"
    ok, meta = getattr(c, method)(**kwargs)
    assert ok is True and meta["result"] == {}

    post.side_effect = RuntimeError("network")
    ok, meta = getattr(c, method)(**kwargs)
    assert ok is False and "network" in meta["error"]


def test_queue_callable_ok_without_mapping_result_and_signature_failure(monkeypatch):
    c = client(queue=Queue([TypeError(), TypeError(), TypeError()]))
    delivered = Mock()
    monkeypatch.setattr(sut, "mark_transport_delivered", delivered)
    monkeypatch.setattr(c, "_http_post", Mock(return_value={"ok": True, "result": "not-mapping"}))
    result = c._queue_callable(
        url="u",
        payload={},
        timeout_s=1,
        delivery_key="key",
        payload_digest="digest",
    )()
    assert result["ok"] is True
    assert delivered.call_args.kwargs["external_id"] is None

    monkeypatch.setattr(sut.inspect, "signature", Mock(side_effect=ValueError("bad signature")))
    assert c._enqueue_transport(
        method="send",
        chat_id="1",
        payload={},
        priority="p",
        critical=False,
        meta={},
        fn=lambda: None,
    ) is False


def test_local_audio_uses_multipart_transport_not_json(tmp_path: Path, monkeypatch, env):
    audio = tmp_path / "private.ogg"
    audio.write_bytes(b"private-audio")
    c = client()
    multipart = Mock(return_value={"ok": True, "result": {"message_id": 71}})
    post = Mock(side_effect=AssertionError("local audio must not use JSON sendAudio"))
    monkeypatch.setattr(sut, "http_multipart_file", multipart)
    monkeypatch.setattr(c, "_http_post", post)

    result = c._http_audio_post(
        url="https://telegram.invalid/bottoken/sendAudio",
        payload={"chat_id": "7", "audio": str(audio), "caption": "cap", "parse_mode": "HTML"},
        timeout_s=60,
    )

    assert result["ok"] is True
    post.assert_not_called()
    assert multipart.call_args.kwargs["path"] == str(audio)
    assert multipart.call_args.kwargs["field_name"] == "audio"
    assert multipart.call_args.kwargs["fields"] == {"chat_id": "7", "caption": "cap", "parse_mode": "HTML"}


def test_remote_audio_preserves_json_transport(monkeypatch, env):
    c = client()
    post = Mock(return_value={"ok": True, "result": {"message_id": 72}})
    multipart = Mock(side_effect=AssertionError("remote Telegram media must preserve JSON/file-id path"))
    monkeypatch.setattr(c, "_http_post", post)
    monkeypatch.setattr(sut, "http_multipart_file", multipart)

    result = c._http_audio_post(
        url="https://telegram.invalid/bottoken/sendAudio",
        payload={"chat_id": "7", "audio": "https://cdn.example/audio.ogg"},
        timeout_s=60,
    )

    assert result["ok"] is True
    post.assert_called_once()
    multipart.assert_not_called()


def test_audio_queue_callable_uses_bound_multipart_request(tmp_path: Path, monkeypatch, env):
    audio = tmp_path / "queued.ogg"
    audio.write_bytes(b"queued-audio")
    c = client(state="state")
    multipart = Mock(return_value={"ok": True, "result": {"message_id": 73}})
    monkeypatch.setattr(c, "_http_audio_post", multipart)
    delivered = Mock()
    monkeypatch.setattr(sut, "mark_transport_delivered", delivered)
    payload = {"chat_id": "7", "audio": str(audio)}
    run = c._queue_callable(
        url="https://telegram.invalid/bottoken/sendAudio",
        payload=payload,
        timeout_s=60,
        delivery_key="audio-key",
        payload_digest="audio-digest",
        request_fn=lambda: c._http_audio_post(
            url="https://telegram.invalid/bottoken/sendAudio",
            payload=payload,
            timeout_s=60,
        ),
    )

    assert run()["ok"] is True
    multipart.assert_called_once()
    assert delivered.call_args.kwargs["external_id"] == "73"
