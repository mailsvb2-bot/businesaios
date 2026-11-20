from types import SimpleNamespace

from interfaces.web.chat_widget import runner_components


def test_noop_does_not_claim_delivery(monkeypatch):
    monkeypatch.setattr(runner_components, "build_config",
                        lambda: SimpleNamespace(mode="configured_noop", endpoint="https://example.invalid"))
    status = runner_components.web_chat_delivery_status()
    assert status["delivery_enabled"] is False
    assert "доставка отключена" in status["label"]


def test_unconfigured_endpoint_is_not_connected(monkeypatch):
    monkeypatch.setattr(runner_components, "build_config",
                        lambda: SimpleNamespace(mode="live", endpoint=""))
    assert runner_components.web_chat_delivery_status()["delivery_enabled"] is False


def test_live_config_is_not_a_delivery_receipt(monkeypatch):
    monkeypatch.setattr(runner_components, "build_config",
                        lambda: SimpleNamespace(mode="live", endpoint="https://example.invalid"))
    status = runner_components.web_chat_delivery_status()
    assert status["delivery_enabled"] is True
    assert "доставлено" not in status["label"].lower()
