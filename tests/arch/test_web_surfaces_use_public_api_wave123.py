from __future__ import annotations

from pathlib import Path


def test_web_package_roots_delegate_to_public_api() -> None:
    roots = [
        Path("app/web/__init__.py"),
        Path("app/web/components/__init__.py"),
        Path("app/web/pages/__init__.py"),
        Path("app/web/pages/demand/__init__.py"),
        Path("app/web/components/demand/__init__.py"),
    ]
    for path in roots:
        text = path.read_text(encoding="utf-8")
        assert "public_api" in text, f"{path} must delegate through public_api"


def test_web_compat_entrypoints_still_import() -> None:
    from app.web import AuthService, Routes, SessionStore, WebApp
    from app.web.components import AutopilotButton
    from app.web.components.demand.business_quality_card import render
    from app.web.components.demand.market_balance_card import render as render_balance
    from app.web.pages import Autopilot
    from app.web.pages.demand.business_quality import load
    from app.web.pages.demand.market_health import load as load_market_health
    from app.web.pages.demand.page_loader import build_page_loader

    assert WebApp is not None
    assert AuthService is not None
    assert Routes is not None
    assert SessionStore is not None
    assert AutopilotButton is not None
    assert callable(render)
    assert callable(render_balance)
    assert Autopilot is not None
    assert callable(load)
    assert callable(load_market_health)
    assert callable(build_page_loader)
