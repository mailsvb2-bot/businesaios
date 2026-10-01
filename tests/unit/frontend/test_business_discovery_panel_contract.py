from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "frontend" / "src"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_business_discovery_panel_is_server_backed_and_epistemically_explicit() -> None:
    panel = _read("BusinessDiscoveryPanel.jsx")
    app = _read("App.jsx")
    assert "Знакомство с бизнесом" in panel
    assert all(
        token in panel
        for token in (
            "Со слов владельца",
            "Подтверждено источником",
            "Есть расхождение с источником",
            "Получено из источника",
            "Не знаю",
            "Пропустить сейчас",
        )
    )
    assert "/business-workspace/discovery" in app
    assert '"X-Idempotency-Key": key' in app
    assert "crypto.randomUUID()" in panel
    assert "onLoad={loadBusinessDiscovery}" in app
    assert "onAssert={assertBusinessDiscovery}" in app


def test_business_discovery_panel_does_not_create_browser_truth_store() -> None:
    panel = _read("BusinessDiscoveryPanel.jsx")
    assert "localStorage" not in panel
    assert "sessionStorage" not in panel
    assert "indexedDB" not in panel
    assert "business_observations" not in panel
    assert "provider-evidence" not in panel
    assert "Пропустить сейчас» ничего не записывает" in panel


def test_business_discovery_panel_supports_all_canonical_value_kinds() -> None:
    panel = _read("BusinessDiscoveryPanel.jsx")
    assert all(
        token in panel
        for token in (
            'field.value_kind === "money_minor"',
            'field.value_kind === "percentage"',
            'field.value_kind === "client_presence"',
            "amount_minor",
            "currency",
            "0–100",
        )
    )


def test_business_discovery_panel_has_responsive_and_reduced_motion_styles() -> None:
    panel = _read("BusinessDiscoveryPanel.jsx")
    styles = _read("BusinessDiscoveryPanel.css")
    assert 'import "./BusinessDiscoveryPanel.css"' in panel
    assert all(
        selector in styles
        for selector in (
            ".discovery-panel",
            ".discovery-question",
            ".discovery-status.verified",
            ".discovery-status.conflict",
            "@media (max-width: 640px)",
            "@media (prefers-reduced-motion: reduce)",
        )
    )
