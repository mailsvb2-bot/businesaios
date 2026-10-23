from __future__ import annotations

import base64
from functools import partial
from types import SimpleNamespace

import pytest

from application.business_flows import visual_creatives as vc
from runtime._internal import llm_transport as lt
from runtime._internal.effect_router import EffectRouter
from runtime._internal.effects_actions.llm_completion_support import call_yandex_art
from runtime._internal.http_transport import DisabledNetworkTransport
from runtime.handler_impl.domains.business_flow_ops import handle_event_series

NOW = 1_800_000_000_000


def test_brief_is_frozen_and_never_invents_facts() -> None:
    a = vc.build_brief("Йога", context="утренняя практика", style="warm", fmt="story")
    assert a == vc.build_brief("Йога", context="утренняя практика", style="warm", fmt="story")
    assert (a.width_ratio, a.height_ratio) == (9, 16) and "Без текста" in a.prompt
    assert a.payload_key != vc.build_brief("Йога", style="warm", fmt="post").payload_key
    assert vc.sanitize_direction("у моря в Сочи за 500", owner_context="йога") == ""
    assert vc.sanitize_direction("спокойный рассвет", owner_context="йога") == "спокойный рассвет"
    assert "http" not in vc.build_brief("Йога", context="см. https://x.example").prompt
    with pytest.raises(ValueError):
        vc.build_brief("Йога", style="neon")
    with pytest.raises(ValueError):
        vc.build_brief(" ")


def test_transport_posts_to_fixed_yandex_hosts_and_polls(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(lt, "sync_post_json", lambda **kw: calls.append(kw) or SimpleNamespace(status=200, json={"id": "op123"}, text=""))
    states = iter([{"done": False}, {"done": True, "response": {"image": base64.b64encode(b"JPG").decode()}}])
    monkeypatch.setattr(lt, "sync_request", lambda **kw: calls.append(kw) or SimpleNamespace(status=200, json=next(states), text=""))
    out = lt.yandex_art_generate(api_key="k", folder_id="b1gfolder", prompt="p", negative="n", sleep=lambda s: None)
    assert out == b"JPG"
    assert calls[0]["url"] == lt.YANDEX_ART_URL and calls[0]["data"]["modelUri"] == "art://b1gfolder/yandex-art/latest"
    assert calls[0]["headers"]["Authorization"] == "Api-Key k" and calls[0]["data"]["messages"][1]["weight"] == -1
    assert calls[1]["url"].startswith("https://operation.api.cloud.yandex.net/operations/op123")
    with pytest.raises(RuntimeError):
        lt.yandex_art_generate(api_key="k", folder_id="../evil", prompt="p")


def test_effect_stores_once_per_payload_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    payload = {"payload_key": "abcdef0123456789", "prompt": "p"}
    assert call_yandex_art(payload=payload, generate=lambda **kw: b"x")["error"] == "disabled"
    monkeypatch.setenv("YANDEX_ART_API_KEY", "k")
    monkeypatch.setenv("YANDEX_ART_FOLDER_ID", "b1gfolder")
    n = []
    gen = lambda **kw: n.append(1) or b"IMG"  # noqa: E731
    first = call_yandex_art(payload=payload, generate=gen)
    again = call_yandex_art(payload=payload, generate=gen)
    assert first["ok"] and first["size"] == 3 and again["replayed"] and len(n) == 1
    assert call_yandex_art(payload={"payload_key": "../x"}, generate=gen)["ok"] is False
    assert EffectRouter(transport=DisabledNetworkTransport()).has_handler("marketing_image_generate")


def test_visual_command_gated_idempotent_and_style_pref(flow, monkeypatch) -> None:
    run = lambda arg: flow.run(partial(handle_event_series, now_ms=NOW), op="visual", arg=arg)[1]  # noqa: E731
    monkeypatch.delenv("YANDEX_ART_FOLDER_ID", raising=False)
    monkeypatch.delenv("YANDEXGPT_FOLDER_ID", raising=False)
    monkeypatch.delenv("YANDEX_FOLDER_ID", raising=False)
    assert "YandexART" in run("Йога")
    monkeypatch.setenv("YANDEX_ART_FOLDER_ID", "b1gfolder")
    assert "запомнен" in run("Йога | style | minimal")
    calls = []
    flow.effects.marketing_image_generate = lambda **kw: calls.append(kw) or {"ok": True, "path": "/d/a.jpeg", "size": 10}
    assert "готово (Минимализм, 1:1)" in run("Йога")
    assert "уже создано" in run("Йога") and len(calls) == 1
    assert "STYLE" not in calls[0]["brief"]["prompt"] and calls[0]["payload_key"]
    flow.effects.marketing_image_generate = lambda **kw: {"ok": False}
    assert "недоступен" in run("Йога | photo | story")
