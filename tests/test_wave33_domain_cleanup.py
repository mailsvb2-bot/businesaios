from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_admin_state_delegates_common_side_effects() -> None:
    src = _read("runtime/_internal/effects_domains/admin_state.py")
    assert "admin_state_support" in src
    assert "emit_toggle_event" in src
    assert "send_optional_notification" in src


def test_sales_domain_delegates_offer_building() -> None:
    src = _read("core/policies/product_domains/sales_domain.py")
    assert "sales_domain_support" in src
    assert "build_offer_action" in src


def test_event_log_uses_observability_helpers() -> None:
    src = _read("core/events/log.py")
    assert "log_observability" in src
    assert "build_system_error_payload" in src
    assert "commit_store_if_supported" in src
