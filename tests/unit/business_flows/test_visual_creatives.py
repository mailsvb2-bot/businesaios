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
    monkeypatch.setattr(
        lt,
        "sync_post_json",
        lambda **kw: calls.append(kw) or SimpleNamespace(status=200, json={"id": "op123"}, text=""),
    )
    states = iter([{"done": False}, {"done": True, "response": {"image": base64.b64encode(b"JPG").decode()}}])
    monkeypatch.setattr(
        lt, "sync_request", lambda **kw: calls.append(kw) or SimpleNamespace(status=200, json=next(states), text="")
    )
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
    flow.effects.marketing_image_generate = lambda **kw: calls.append(kw) or {
        "ok": True,
        "path": "/d/a.jpeg",
        "size": 10,
    }
    assert "готово (Минимализм, 1:1)" in run("Йога")
    assert "уже создано" in run("Йога") and len(calls) == 1
    assert "STYLE" not in calls[0]["brief"]["prompt"] and calls[0]["payload_key"]
    flow.effects.marketing_image_generate = lambda **kw: {"ok": False}
    assert "недоступен" in run("Йога | photo | story")


# --- frozen readers, ranking, normalization ---
import json as _json  # noqa: E402

import pytest as _pytest  # noqa: E402

from application.business_flows import visual_creatives as _vc  # noqa: E402
from application.business_flows import visual_scene as _vs  # noqa: E402


class _St:
    composition, realism = "story_scene", "realistic"

    def to_mapping(self) -> dict[str, object]:
        return {}


def test_frozen_scene_and_binding() -> None:
    c, src, vs = _vs.deterministic_visual_scene_bundle(request="кот", semantic_flags=(), style_intent=_St())
    raw = {
        "version": 4,
        "kind": "image",
        "brief": {"scene_contract": c.to_mapping()},
        "intent": {"scene_planner_source": src, "scene_variant": vs[0].to_mapping()},
        "binding": {"type": "event_content", "event_id": "e1", "stage": "warmup", "slot_key": "s", "kind": "image"},
    }
    assert _vc.frozen_scene(_json.dumps(raw)) == (c, src, vs[0])
    assert _vc.frozen_binding(_json.dumps(raw))["event_id"] == "e1"
    assert _vc.frozen_scene(_json.dumps({**raw, "version": 3})) is None
    assert _vc.frozen_binding(_json.dumps({"version": 1})) is None
    with _pytest.raises(ValueError):
        _vc.frozen_binding(_json.dumps({**raw, "kind": "video"}))


def test_best_candidate_prefers_qa_pass() -> None:
    jobs = [
        {"id": 1, "status": "failed"},
        {"id": 2, "status": "succeeded", "semantic_qa": "needs_review"},
        {"id": 3, "status": "succeeded", "semantic_qa": "pass"},
        {"id": 4, "status": "succeeded"},
    ]
    assert _vc.best_candidate(jobs)["id"] == 3
    assert _vc.best_candidate([{"id": 1, "status": "failed"}])["id"] == 1
    assert _vc.best_candidate([]) is None


def test_normalize_trims_blank_band(tmp_path) -> None:
    pil = _pytest.importorskip("PIL.Image")
    img = pil.new("RGB", (400, 400), (255, 255, 255))
    img.paste((200, 30, 30), (20, 20, 380, 150))
    p = tmp_path / "a.png"
    img.save(p)
    out = _vc.normalize_image(p)
    with pil.open(out) as done:
        assert done.height < 300 and done.mode == "RGB"
    tiny = tmp_path / "t.png"
    pil.new("RGB", (10, 10)).save(tiny)
    with _pytest.raises(ValueError, match="dimensions"):
        _vc.normalize_image(tiny)


# ---- creative-generation receipts, scene-plan receipts, style clear, aesthetic director ----
def _prep(led=None, member="m1", request="Фото кофейни", now=1_800_000_000_000, **kw):
    from application.business_flows import visual_creatives as v

    led = led if led is not None else v.gen_replay([])
    payload = v.freeze_payload(request=request, kind="image", brand_context="тёплый стиль", country_code="RU")
    r, facts = v.gen_prepare(
        led,
        member,
        request_text=request,
        brand_context="тёплый стиль",
        country_code="RU",
        provider_payload_json=payload,
        now_ms=now,
        **kw,
    )
    return v.gen_replay(facts, into=led), r, facts


def test_gen_prepare_is_idempotent_and_replaces_a_different_prepared_receipt() -> None:
    from application.business_flows import visual_creatives as v

    led, r, facts = _prep()
    assert [f["step"] for f in facts] == ["gen_prepared"] and r.status == "prepared"
    assert r.idempotency_key.startswith("clientplatform:owner-image:")
    led2, r2, facts2 = _prep(led)
    assert r2.id == r.id and facts2 == []  # identical request: no new receipt
    led3, r3, facts3 = _prep(led2, request="Фото булочной")
    assert [f["step"] for f in facts3] == ["gen_deleted", "gen_prepared"] and r3.id != r.id
    assert v.gen_active(led3, "m1").id == r3.id
    with pytest.raises(LookupError):
        v.gen_get(led3, "other-member", r3.id)


def test_gen_lifecycle_submit_deliver_redeliver_abandon() -> None:
    from application.business_flows import visual_creatives as v

    led, r, _ = _prep()
    now = 1_800_000_000_000
    cur, fs = v.gen_begin_submission(led, "m1", r.id, now_ms=now)
    led = v.gen_replay(fs, into=led)
    assert cur.status == "prepared" and v.gen_get(led, "m1", r.id).status == "submitting"
    assert v.gen_begin_submission(led, "m1", r.id, now_ms=now)[1] == []  # never submit twice
    _, fs = v.gen_remember_job(led, "m1", r.id, source_job_id="job1", provider_status="succeeded", now_ms=now)
    led = v.gen_replay(fs, into=led)
    assert v.gen_get(led, "m1", r.id).status == "succeeded"
    assert v.gen_authorize_redelivery(led, "m1", r.id, now_ms=now) == (False, [])  # nothing claimed yet
    ok, fs = v.gen_claim_delivery(led, "m1", r.id, now_ms=now)
    led = v.gen_replay(fs, into=led)
    assert ok and v.gen_claim_delivery(led, "m1", r.id, now_ms=now) == (False, [])
    ok, fs = v.gen_authorize_redelivery(led, "m1", r.id, now_ms=now + 1)
    led = v.gen_replay(fs, into=led)
    ok, fs = v.gen_claim_delivery(led, "m1", r.id, now_ms=now + 2)
    led = v.gen_replay(fs, into=led)
    assert ok
    fresh, fresh_r, _ = _prep()
    with pytest.raises(ValueError):  # delivery must be claimed before it can be marked delivered
        v.gen_mark_delivered(fresh, "m1", fresh_r.id, now_ms=1)
    _, fs = v.gen_mark_delivered(led, "m1", r.id, now_ms=now + 3)
    led = v.gen_replay(fs, into=led)
    assert v.gen_active(led, "m1") is None


def test_gen_failure_handling_definitive_deletes_ambiguous_stays_active() -> None:
    from application.business_flows import visual_creatives as v

    for code, active in (("", False), (sorted(v.GEN_AMBIGUOUS_ERRORS)[0], True)):
        led, r, _ = _prep()
        _, fs = v.gen_remember_job(
            led, "m1", r.id, source_job_id="j", provider_status="failed", provider_error_code=code, now_ms=1
        )
        led = v.gen_replay(fs, into=led)
        assert (v.gen_active(led, "m1") is not None) is active
        if active:
            assert v.gen_get(led, "m1", r.id).status == "running"
            assert v.gen_abandon_ambiguous(led, "m1", r.id, job_status="running", job_error_code=code) == (False, [])
            ok, fs = v.gen_abandon_ambiguous(led, "m1", r.id, job_status="failed", job_error_code=code)
            assert ok and fs[0]["step"] == "gen_deleted"
    led, r, _ = _prep()
    with pytest.raises(ValueError):
        v.gen_remember_job(led, "m1", r.id, source_job_id="", provider_status="queued", now_ms=1)
    with pytest.raises(ValueError):
        v.gen_remember_job(led, "m1", r.id, source_job_id="j", provider_status="weird", now_ms=1)


def test_gen_abandon_only_discards_finished_result_and_payload_is_validated() -> None:
    from application.business_flows import visual_creatives as v

    led, r, _ = _prep()
    assert v.gen_abandon(led, "m1", r.id) == (False, [])
    with pytest.raises(ValueError):
        v.gen_prepare(
            led, "m1", request_text="", brand_context="", country_code="", provider_payload_json="{}", now_ms=1
        )
    with pytest.raises(ValueError):
        v.gen_prepare(
            led, "m1", request_text="x", brand_context="", country_code="RUS", provider_payload_json="{}", now_ms=1
        )


def test_freeze_payload_is_deterministic_and_bound() -> None:
    from application.business_flows import visual_creatives as v

    b = {"type": "event_content", "event_id": "e", "stage": "warmup", "slot_key": "k", "kind": "image"}
    a = v.freeze_payload(request="Йога утром", kind="image", brand_context="", country_code="ru", binding=b)
    assert a == v.freeze_payload(request="Йога утром", kind="image", brand_context="", country_code="ru", binding=b)
    assert v.frozen_binding(a) == b and v.frozen_scene(a)[1] == "deterministic"
    with pytest.raises(ValueError):
        v.freeze_payload(request="", kind="image")
    with pytest.raises(ValueError):
        v.freeze_payload(request="x", kind="gif")


def test_scene_plan_receipts_claim_once_complete_and_ambiguous() -> None:
    from application.business_flows import visual_creatives as v

    style = {"look": "warm"}
    plans: dict = {}
    r, fresh, fs = v.scene_plan_claim(plans, "m", request="Кофе", style_intent=style)
    assert fresh and r["status"] == "planning"
    plans = v.scene_plan_replay(fs)
    assert v.scene_plan_claim(plans, "m", request="Кофе", style_intent=style)[1:] == (False, [])
    assert v.scene_plan_get(plans, "m", request="Кофе", style_intent={"look": "cold"}) is None
    done, fs2 = v.scene_plan_complete(plans, "m", r["id"], result_json='{"a":1}')
    plans = v.scene_plan_replay(fs + fs2)
    assert done["status"] == "ready" and plans[next(iter(plans))]["result_json"] == '{"a":1}'
    with pytest.raises(ValueError):
        v.scene_plan_complete(plans, "m", r["id"], result_json="{}")  # already finished
    r2, _, fs3 = v.scene_plan_claim({}, "m", request="Чай", style_intent=style)
    plans2 = v.scene_plan_replay(fs3)
    amb, fs4 = v.scene_plan_mark_ambiguous(plans2, "m", r2["id"])
    assert (
        amb["status"] == "ambiguous"
        and v.scene_plan_mark_ambiguous(v.scene_plan_replay(fs3 + fs4), "m", r2["id"])[1] == []
    )
    with pytest.raises(LookupError):
        v.scene_plan_mark_ambiguous(plans2, "m", "nope")


def test_clear_style_removes_only_a_stored_preference() -> None:
    from application.business_flows import visual_creatives as v

    st = v.replay([v.save_style("Йога", "minimal")])
    ok, fs = v.clear_style("Йога", st)
    assert ok and v.replay([v.save_style("Йога", "minimal"), *fs]).styles == {}
    assert v.clear_style("Йога", v.replay([])) == (False, [])


class _Chat:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def chat(self, messages, **kw):
        self.calls.append(messages)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_aesthetic_director_is_off_by_default_and_sanitizes() -> None:
    from application.business_flows import visual_creatives as v

    good = '{"subject":"чашка кофе","light":"мягкий утренний свет","style":"тёплая плёнка"}'
    chat = _Chat(good)
    assert v.direct_aesthetics(chat, owner_request="кофе", kind="image", env={}) is None and chat.calls == []
    on = {"VISUAL_AESTHETIC_DIRECTOR_ENABLED": "1"}
    out = v.direct_aesthetics(chat, owner_request="кофе", kind="image", env=on)
    assert out["subject"] == "чашка кофе" and len(" ".join(x for x in out.values() if x)) <= 350
    assert v.direct_aesthetics(_Chat(RuntimeError("down")), owner_request="кофе", kind="image", env=on) is None
    assert v.direct_aesthetics(_Chat("not json"), owner_request="кофе", kind="image", env=on) is None
    assert (
        v.direct_aesthetics(_Chat('{"price":"-50%"}'), owner_request="кофе", kind="image", env=on) is None
    )  # unknown keys
    assert v.direct_aesthetics(_Chat('{"subject":""}'), owner_request="кофе", kind="image", env=on) is None
    assert v.direct_aesthetics(None, owner_request="кофе", kind="image", env=on) is None


# --- video through the provider port: Russian providers only, idempotent, off by default ---
def test_video_mode_is_off_by_default_and_provider_allowlist_matches_executor() -> None:
    from runtime._internal.effects_domains import marketing

    assert vc.video_generation_mode({}) == "unavailable"
    assert vc.video_generation_mode({vc.VIDEO_ENV: "1"}) == "motion"
    assert vc.video_generation_mode({vc.VIDEO_ENV: "1"}, country_code="US") == "unavailable"
    assert vc.VIDEO_PROVIDER_ALLOW == marketing.VIDEO_PROVIDER_ALLOW
    for foreign in ("veo", "runway", "sora", "kling"):
        with pytest.raises(ValueError, match="video_provider_not_allowed"):
            vc.freeze_video_payload(request="Ролик про йогу", preferred_provider=foreign)


def test_video_freeze_and_create_once_through_fake_port() -> None:
    payload = vc.freeze_video_payload(request="Ролик про вебинар по йоге", preferred_provider="yandexart_motion",
                                      duration_seconds=99, binding={"type": "event_content", "event_id": "e1",
                                                                    "stage": "s", "slot_key": "k", "kind": "video"})
    assert vc.freeze_video_payload(request="Ролик про вебинар по йоге", preferred_provider="yandexart_motion",
                                   duration_seconds=99, binding={"type": "event_content", "event_id": "e1",
                                                                 "stage": "s", "slot_key": "k", "kind": "video"}) == payload
    assert '"duration_seconds":15' in payload and vc.frozen_binding(payload)["kind"] == "video"
    port, key = vc.FakeVideoProvider(), vc.video_idempotency_key("t1", payload)
    a = vc.create_video_from_frozen_payload(provider_payload_json=payload, scope_id="t1", idempotency_key=key, provider=port)
    b = vc.create_video_from_frozen_payload(provider_payload_json=payload, scope_id="t1", idempotency_key=key, provider=port)
    assert a == b and len(port.calls) == 1 and port.calls[0]["preferred_provider"] == "yandexart_motion"
    fact = vc.video_requested_fact("t1", payload, a, now_ms=1)
    assert vc.video_already_requested([fact], key)["job_id"] == a["job_id"]
    dry = vc.video_requested_fact("t1", payload, {"status": "dry_run"}, now_ms=1)
    assert vc.video_already_requested([dry], key) is None  # a dry run never blocks the real request later


def test_video_rejects_image_payload_foreign_provider_and_missing_key() -> None:
    port = vc.FakeVideoProvider()
    image = vc.freeze_payload(request="Фото йоги", kind="image")
    with pytest.raises(ValueError, match="invalid"):
        vc.create_video_from_frozen_payload(provider_payload_json=image, scope_id="t", idempotency_key="k", provider=port)
    ok = vc.freeze_video_payload(request="Ролик про йогу")
    tampered = ok.replace('"preferred_provider":""', '"preferred_provider":"veo"')
    with pytest.raises(ValueError, match="video_provider_not_allowed"):
        vc.create_video_from_frozen_payload(provider_payload_json=tampered, scope_id="t", idempotency_key="k", provider=port)
    with pytest.raises(ValueError):
        vc.create_video_from_frozen_payload(provider_payload_json=ok, scope_id="t", idempotency_key="", provider=port)
    assert port.calls == []

    class Failing(vc.VideoProviderPort):
        def submit(self, **kw):
            return {"ok": False, "reason": "provider_down"}

    with pytest.raises(RuntimeError, match="provider_down"):
        vc.create_video_from_frozen_payload(provider_payload_json=ok, scope_id="t", idempotency_key="k", provider=Failing())
