from __future__ import annotations

from collections.abc import Iterable

import pytest

from runtime._internal.effects_actions import weather_actions


class FakeEventLog:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, **event) -> None:
        self.events.append(dict(event))


class FakeWeatherEffects(weather_actions.WeatherEffectsMixin):
    def __init__(self) -> None:
        self.event_log = FakeEventLog()
        self.delivery_calls: list[dict] = []
        self.weather_calls: list[str] = []

    def _open_meteo_weather(self, city: str):
        self.weather_calls.append(city)
        return True, f"Weather for {city}", {"provider": "open-meteo"}

    def send_message(self, **kwargs):
        self.delivery_calls.append(dict(kwargs))
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
                "external_refs": ["weather-message-1"],
                "confidence": 1.0,
            },
        }


@pytest.fixture(autouse=True)
def _executor_guard(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    monkeypatch.setattr(weather_actions, "assert_called_from_executor", lambda: None)
    yield


def test_missing_city_fails_closed_without_amsterdam_fallback() -> None:
    effects = FakeWeatherEffects()

    with pytest.raises(RuntimeError, match="WEATHER_CITY_REQUIRED"):
        effects.send_weather(
            decision_id="decision-weather",
            correlation_id="correlation-weather",
            tenant_id="business-a",
            user_id="user-1",
            city="   ",
        )

    assert effects.weather_calls == []
    assert effects.delivery_calls == []
    assert effects.event_log.events == []


def test_weather_delivery_preserves_business_tenant_scope_and_connector_proof() -> None:
    effects = FakeWeatherEffects()

    result = effects.send_weather(
        decision_id="decision-weather",
        correlation_id="correlation-weather",
        tenant_id="business-a",
        user_id="user-1",
        city="Berlin",
    )

    assert effects.weather_calls == ["Berlin"]
    assert effects.delivery_calls[-1]["tenant_id"] == "business-a"
    assert effects.delivery_calls[-1]["user_id"] == "user-1"
    assert effects.event_log.events[-1]["event_type"] == "weather_sent"
    assert effects.event_log.events[-1]["payload"]["tenant_id"] == "business-a"
    assert effects.event_log.events[-1]["payload"]["city"] == "Berlin"
    assert result["ok"] is True
    assert result["router_evidence"]["source"] == "connector"
