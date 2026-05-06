from __future__ import annotations

from pathlib import Path


def test_internal_web_surfaces_do_not_import_removed_page_builder_shims() -> None:
    checked = [
        Path('app/web/routes.py'),
        Path('app/web/pages/__init__.py'),
    ]
    for path in checked:
        text = path.read_text(encoding='utf-8')
        assert 'app.web.pages.page_builders' not in text


def test_page_builder_symbols_live_on_package_root() -> None:
    import app.web.pages as pages

    assert pages.Autopilot.KIND == 'autopilot'
    assert pages.Dashboard.KIND == 'dashboard'
    assert pages.Settings.KIND == 'settings'
