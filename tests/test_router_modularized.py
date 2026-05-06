from pathlib import Path


def test_router_is_modularized_and_small():
    router = Path("core/policies/telegram/router.py").read_text(encoding="utf-8")
    assert "handle_settings_routes" in router
    assert "handle_command_routes" in router
    assert "handle_marketing_routes" in router
    assert len(router.splitlines()) < 140
