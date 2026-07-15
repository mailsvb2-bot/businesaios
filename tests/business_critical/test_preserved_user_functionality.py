from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime._internal.effects_actions.payments import access
from runtime.handler_impl.domains.user_ops import (
    handle_log_mood,
    handle_send_audio,
)
from runtime.handlers import growth_propose as growth_propose_handler
from runtime.handlers import reward_observe as reward_observe_handler


class FakeEffects:
    def __init__(self, event_log=None) -> None:
        self.event_log = event_log
        self.calls: list[tuple[str, dict]] = []

    def send_audio(self, **kwargs):
        self.calls.append(("send_audio", dict(kwargs)))
        return {"ok": True}

    def log_mood(self, **kwargs):
        self.calls.append(("log_mood", dict(kwargs)))
        return {"ok": True}

    def send_message(self, **kwargs):
        self.calls.append(("send_message", dict(kwargs)))
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
            },
        }


class FakeStore:
    def __init__(self, events: list[dict]) -> None:
        self.events = events

    def iter_events(self, **_kwargs):
        return list(self.events)


class FakeEventLog:
    tenant_id = "business-a"

    def __init__(self, events: list[dict]) -> None:
        self._store = FakeStore(events)
        self.events = events

    def emit(self, **event):
        normalized = {
            "event_type": event["event_type"],
            "payload": dict(event.get("payload") or {}),
            **dict(event),
        }
        self.events.append(normalized)
        return {"event_id": f"event-{len(self.events)}"}


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            payload={},
        )
    )


def _strict_env(action: str) -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            issuer_id="businesaios-core",
            action=str(action),
            payload={},
        )
    )


class CanonicalEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict, *, commit: bool = True) -> None:
        event_id = str(event.get("event_id") or "")
        if any(str(row.get("event_id") or "") == event_id for row in self.events):
            raise RuntimeError("duplicate event_id")
        self.events.append(dict(event))

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        event_type: str | None = None,
        event_types=None,
        user_id: str | None = None,
        limit: int | None = None,
    ):
        allowed = {str(item) for item in (event_types or ()) if str(item)}
        if event_type:
            allowed.add(str(event_type))
        rows = []
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if allowed and str(event.get("event_type") or "") not in allowed:
                continue
            if user_id is not None and str(event.get("user_id") or "") != str(user_id):
                continue
            timestamp_ms = int(event.get("timestamp_ms") or 0)
            if timestamp_ms < int(start_ms):
                continue
            if end_ms is not None and timestamp_ms >= int(end_ms):
                continue
            rows.append(dict(event))
        if limit is not None:
            rows = rows[: int(limit)]
        return iter(rows)

    def commit(self) -> None:
        return None


class SequencedDeliveryEffects:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send_message(self, **kwargs):
        self.messages.append(dict(kwargs))
        ok = len(self.messages) > 1
        return {
            "ok": ok,
            "evidence": {
                "source": "connector",
                "verified": ok,
                "status": "verified" if ok else "failed",
                "external_refs": ["message-2"] if ok else [],
                "confidence": 1.0 if ok else 0.0,
            },
        }


@pytest.mark.lock
def test_audio_and_mood_handlers_preserve_tenant_and_channel() -> None:
    effects = FakeEffects()

    handle_send_audio(
        {
            "tenant_id": "business-a",
            "user_id": "user-1",
            "path": "https://cdn.example/audio.ogg",
            "channel": "telegram",
        },
        effects,
        _env(),
    )
    handle_log_mood(
        {
            "tenant_id": "business-a",
            "user_id": "user-1",
            "score": 8,
            "channel": "whatsapp",
            "channel_policy": {"fallback_channels": ["sms", "email"]},
        },
        effects,
        _env(),
    )

    audio = effects.calls[0][1]
    mood = effects.calls[1][1]
    assert audio["tenant_id"] == "business-a"
    assert audio["channel"] == "telegram"
    assert mood["tenant_id"] == "business-a"
    assert mood["channel"] == "whatsapp"
    assert mood["channel_policy"] == {
        "fallback_channels": ["sms", "email"]
    }


@pytest.mark.lock
def test_invalid_gift_does_not_grant_entitlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(access, "assert_called_from_executor", lambda: None)
    event_log = FakeEventLog([])
    effects = FakeEffects(event_log)

    result = access.grant_access_effect(
        effects,
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="business-a",
        product_id="product-a",
        user_id="user-1",
        track_event_type="gift_redeemed",
        track_payload={"token": "missing"},
        channel="whatsapp",
        channel_policy={"fallback_channels": ["sms", "email"]},
    )

    assert result["ok"] is False
    assert result["reason"] == "not_found"
    assert not any(
        event["event_type"] == "entitlement_granted"
        for event in event_log.events
    )
    notification = effects.calls[-1][1]
    assert notification["channel"] == "whatsapp"
    assert notification["channel_policy"] == {
        "fallback_channels": ["sms", "email"]
    }


@pytest.mark.lock
def test_valid_gift_uses_canonical_entitlement_primitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(access, "assert_called_from_executor", lambda: None)
    initial = [
        {
            "event_type": "gift_token_created",
            "payload": {
                "token": "gift-1",
                "created_by": "admin-1",
                "expires_ms": 0,
            },
        }
    ]
    event_log = FakeEventLog(initial)
    effects = FakeEffects(event_log)

    result = access.grant_access_effect(
        effects,
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="business-a",
        product_id="product-a",
        user_id="user-1",
        track_event_type="gift_redeemed",
        track_payload={"token": "gift-1"},
    )

    assert result["ok"] is True
    assert result["entitlement"]["grant_key"] == "gift-1"
    assert [
        event["event_type"]
        for event in event_log.events
    ][-2:] == ["gift_redeemed", "entitlement_granted"]


@pytest.mark.lock
def test_reward_observe_uses_canonical_reward_and_reuses_durable_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CanonicalEventStore()
    effects = SequencedDeliveryEffects()
    compute_calls = 0

    class FakeRewardComputer:
        def __init__(self, **_kwargs) -> None:
            pass

        def transition_for_decision(self, **_kwargs):
            nonlocal compute_calls
            compute_calls += 1
            return SimpleNamespace(
                reward_minor=125,
                state={"profit_minor": 1125},
                action={"kind": "ads.plan"},
                meta={"source": "canonical_profit_metrics"},
            )

    monkeypatch.setattr(
        reward_observe_handler,
        "ProfitMetricsService",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        reward_observe_handler,
        "RewardComputer",
        FakeRewardComputer,
    )

    payload = {
        "tenant_id": "business-a",
        "user_id": "owner-1",
        "metrics": {"source_decision_id": "ads-decision-1"},
        "channel": "whatsapp",
        "channel_policy": {"fallback_channels": ["sms", "email"]},
    }
    first = reward_observe_handler.handle_reward_observe(
        payload,
        effects,
        _strict_env("reward_observe@v1"),
        event_store=store,
    )
    second = reward_observe_handler.handle_reward_observe(
        payload,
        effects,
        _strict_env("reward_observe@v1"),
        event_store=store,
    )

    assert compute_calls == 1
    assert first["ok"] is False
    assert first["router_evidence"] is None
    assert second["ok"] is True
    assert second["router_evidence"]["source"] == "ledger"
    assert first["completion_event_id"] == second["completion_event_id"]
    assert len(
        [event for event in store.events if event["event_type"] == "reward_observe@v1"]
    ) == 1
    assert effects.messages[-1]["channel"] == "whatsapp"
    assert effects.messages[-1]["channel_policy"] == {
        "fallback_channels": ["sms", "email"]
    }


@pytest.mark.lock
def test_growth_propose_delegates_to_canonical_strategy_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict = {}

    def fake_generate(payload, effects, env, **kwargs):
        seen["payload"] = dict(payload)
        seen["kwargs"] = dict(kwargs)
        return {
            "ok": True,
            "status": "verified",
            "plan": SimpleNamespace(top_hypotheses=(object(), object())),
            "router_evidence": {"source": "ledger", "verified": True},
        }

    monkeypatch.setattr(
        growth_propose_handler,
        "handle_growth_strategy_generate",
        fake_generate,
    )
    payload = {
        "tenant_id": "business-a",
        "user_id": "owner-1",
        "objective": "increase qualified leads",
        "signals": {"conversion_rate": 0.015, "roas": 2.4},
        "channel": "instagram",
        "channel_policy": {"fallback_channels": ["messenger", "email"]},
    }
    result = growth_propose_handler.handle_growth_propose(
        payload,
        FakeEffects(),
        _strict_env("growth_propose@v1"),
        event_store=object(),
        llm="canonical-llm",
    )

    assert result["ok"] is True
    assert result["queued"] == 2
    assert result["compatibility_action"] == "growth_propose@v1"
    assert seen["kwargs"]["track_event_type"] == "growth_propose@v1"
    assert seen["kwargs"]["llm"] == "canonical-llm"
    assert seen["payload"]["channel"] == "instagram"
    assert seen["payload"]["channel_policy"] == {
        "fallback_channels": ["messenger", "email"]
    }
    assert seen["payload"]["goal"]["constraints"] == (
        "objective:increase qualified leads",
        "signal:conversion_rate=0.015",
        "signal:roas=2.4",
    )
