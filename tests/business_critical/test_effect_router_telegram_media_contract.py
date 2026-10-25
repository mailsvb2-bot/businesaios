"""EffectRouter media effects: the client gets exactly the payload values; empty targets are rejected before the client."""

from __future__ import annotations

import asyncio

import pytest

from runtime._internal.effect_payloads import EffectPayloadError
from runtime._internal.effect_router import EffectRouter
from runtime._internal.effects_clients import telegram_client as tc
from runtime.platform.delivery_state import DeliveryState

PHOTO = "TELEGRAM_SEND_PHOTO"
AUDIO = "TELEGRAM_SEND_AUDIO"

# Gaps of the concrete client (defence in depth). Strict: while listed the gap must really exist; a fix removes the entry.
KNOWN_CLIENT_GAPS = {
    "send_photo_empty_chat_id": "REAL DEFECT: TelegramClient.send_photo posts chat_id='' to the Bot API when a token is set",
    "send_photo_empty_photo_url": "REAL DEFECT: TelegramClient.send_photo posts photo='' to the Bot API when a token is set",
}


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def send_photo(self, **kwargs):
        self.calls.append(("send_photo", kwargs))
        return True, {"mode": "fake", "external_id": "1"}

    def send_audio(self, **kwargs):
        self.calls.append(("send_audio", kwargs))
        return True, {"mode": "fake", "external_id": "2"}


@pytest.fixture
def fake(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(EffectRouter, "_telegram_client", lambda self: client)  # slots dataclass: patch the class
    return client


def _run(action: str, payload: dict) -> dict:
    return asyncio.run(EffectRouter(transport=object()).execute(action, payload))


def test_send_photo_forwards_exact_chat_id_photo_url_and_caption(fake) -> None:
    out = _run(PHOTO, {"chat_id": "4242", "photo_url": "https://cdn.example/a.png", "caption": "подпись"})
    assert out["ok"] is True
    (name, kwargs), = fake.calls
    assert name == "send_photo"
    assert kwargs["chat_id"] == "4242"
    assert kwargs["photo_url"] == "https://cdn.example/a.png"
    assert kwargs["caption"] == "подпись"


def test_send_photo_never_swaps_or_blanks_arguments(fake) -> None:
    _run(PHOTO, {"chat_id": "7", "photo_url": "file_id_ABC"})
    _run(PHOTO, {"chat_id": "8", "photo_url": "https://cdn.example/b.png"})
    assert [(c["chat_id"], c["photo_url"]) for _n, c in fake.calls] == [("7", "file_id_ABC"), ("8", "https://cdn.example/b.png")]


@pytest.mark.parametrize("missing", ["chat_id", "photo_url"])
@pytest.mark.parametrize("blank", ["", "   ", None])
def test_send_photo_rejects_empty_target_before_the_client(fake, missing, blank) -> None:
    payload = {"chat_id": "4242", "photo_url": "https://cdn.example/a.png", missing: blank}
    with pytest.raises(EffectPayloadError, match=missing):
        _run(PHOTO, payload)
    assert fake.calls == []


def test_send_photo_rejects_absent_keys(fake) -> None:
    for payload in ({"photo_url": "https://cdn.example/a.png"}, {"chat_id": "1"}, {}):
        with pytest.raises(EffectPayloadError):
            _run(PHOTO, payload)
    assert fake.calls == []


def test_send_audio_forwards_exact_values_and_rejects_empty(fake) -> None:
    _run(AUDIO, {"chat_id": "55", "audio_url": "https://cdn.example/a.mp3"})
    (_n, kwargs), = fake.calls
    assert (kwargs["chat_id"], kwargs["audio_url"]) == ("55", "https://cdn.example/a.mp3")
    for payload in ({"chat_id": "", "audio_url": "https://cdn.example/a.mp3"}, {"chat_id": "55", "audio_url": ""}):
        with pytest.raises(EffectPayloadError):
            _run(AUDIO, payload)
    assert len(fake.calls) == 1


@pytest.fixture
def real_client(monkeypatch, tmp_path):
    client = tc.TelegramClient(transport=object(), delivery_state=DeliveryState(db_path=tmp_path / "p.sqlite"))
    monkeypatch.setattr(tc, "_token", lambda: "TEST")
    posts: list[dict] = []
    monkeypatch.setattr(client, "_http_post", lambda **kw: posts.append(kw) or {"ok": True, "result": {"message_id": 1}})
    return client, posts


def test_client_send_photo_posts_exact_values(real_client) -> None:
    client, posts = real_client
    ok, _meta = client.send_photo(chat_id="42", photo_url="https://cdn.example/a.png")
    assert ok is True
    assert posts[0]["payload"] == {"chat_id": "42", "photo": "https://cdn.example/a.png"}
    assert posts[0]["url"].endswith("/botTEST/sendPhoto")


@pytest.mark.parametrize(
    ("gap", "kwargs"),
    [
        ("send_photo_empty_chat_id", {"chat_id": "", "photo_url": "https://cdn.example/a.png"}),
        ("send_photo_empty_photo_url", {"chat_id": "42", "photo_url": ""}),
    ],
)
def test_client_send_photo_empty_target_is_a_known_gap_until_fixed(real_client, gap, kwargs) -> None:
    client, posts = real_client
    ok, _meta = client.send_photo(**kwargs)
    rejected = ok is False and posts == []
    if gap in KNOWN_CLIENT_GAPS:
        assert not rejected, f"{gap} is fixed: remove it from KNOWN_CLIENT_GAPS"
    else:
        assert rejected


def test_email_payload_keeps_values_and_rejects_empty_fields() -> None:
    from contracts.email_outbound import EmailOutboundPayloadV1

    ok = EmailOutboundPayloadV1(recipient=" A@Example.com ", subject="  Привет   мир ", body=" текст ")
    assert (ok.recipient, ok.subject, ok.body) == ("a@example.com", "Привет мир", "текст")
    for kwargs in (
        {"recipient": "", "subject": "s", "body": "b"},
        {"recipient": "not-an-address", "subject": "s", "body": "b"},
        {"recipient": "a@example.com", "subject": "  ", "body": "b"},
        {"recipient": "a@example.com", "subject": "s", "body": "\x00 "},
    ):
        with pytest.raises(ValueError):
            EmailOutboundPayloadV1(**kwargs)
