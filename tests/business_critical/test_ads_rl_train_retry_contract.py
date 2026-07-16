from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.handlers import ads_rl_train_tick


class InMemoryEventStore:
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
            rows.append(dict(event))
        if limit is not None:
            rows = rows[: int(limit)]
        return iter(rows)

    def commit(self) -> None:
        return None


class SequencedEffects:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.events: list[dict] = []

    def send_message(self, **kwargs):
        self.messages.append(dict(kwargs))
        if len(self.messages) == 1:
            return {
                "ok": False,
                "status": "failed",
                "evidence": {
                    "source": "connector",
                    "verified": False,
                    "status": "failed",
                    "external_refs": [],
                    "confidence": 0.0,
                },
            }
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
                "external_refs": ["message-rl-train-2"],
                "confidence": 1.0,
            },
        }

    def track_event(self, **kwargs):
        self.events.append(dict(kwargs))
        return {"ok": True}


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-rl-train",
            correlation_id="correlation-rl-train",
        )
    )


@pytest.mark.lock
def test_delivery_retry_reuses_completed_policy_without_second_training(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryEventStore()
    effects = SequencedEffects()
    train_calls = 0

    monkeypatch.setattr(ads_rl_train_tick, "bind_runtime_state", lambda **_kwargs: None)
    monkeypatch.setattr(
        ads_rl_train_tick.maturity_gate,
        "is_mature",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        ads_rl_train_tick,
        "ProfitMetricsService",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        ads_rl_train_tick,
        "RewardComputer",
        lambda **_kwargs: object(),
    )

    class FakeDatasetBuilder:
        def __init__(self, **_kwargs) -> None:
            pass

        def build_for_decisions(self, **_kwargs):
            return [object()] * 5

    class FakeTrainer:
        def __init__(self, **_kwargs) -> None:
            pass

        def train(self, **kwargs):
            nonlocal train_calls
            train_calls += 1
            assert kwargs["decision_id"] == "decision-rl-train"
            assert kwargs["correlation_id"] == "correlation-rl-train"
            assert kwargs["user_id"] == "owner-1"
            return SimpleNamespace(
                ok=True,
                reason="trained",
                n=5,
                policy_version=7,
                ope_reason="ok",
                avg_reward_minor=125.0,
            )

    monkeypatch.setattr(ads_rl_train_tick, "DatasetBuilder", FakeDatasetBuilder)
    monkeypatch.setattr(ads_rl_train_tick, "RLTrainer", FakeTrainer)

    payload = {
        "tenant_id": "business-a",
        "user_id": "owner-1",
        "decision_ids": [f"source-decision-{index}" for index in range(5)],
        "min_matured": 5,
        "min_transitions": 1,
    }

    first = ads_rl_train_tick.handle_ads_rl_train_tick(
        payload,
        effects,
        _env(),
        event_store=store,
    )
    second = ads_rl_train_tick.handle_ads_rl_train_tick(
        payload,
        effects,
        _env(),
        event_store=store,
    )

    assert train_calls == 1
    assert first["ok"] is False
    assert first["router_evidence"] is None
    assert second["ok"] is True
    assert second["status"] == "verified"
    assert first["completion_event_id"] == second["completion_event_id"]
    assert second["router_evidence"]["source"] == "ledger"
    assert second["delivery"]["evidence"]["external_refs"] == [
        "message-rl-train-2"
    ]
    completion_events = [
        event
        for event in store.events
        if event.get("event_type") == "ads_rl_train_completed@v1"
    ]
    assert len(completion_events) == 1
    assert completion_events[0]["decision_id"] == "decision-rl-train"
