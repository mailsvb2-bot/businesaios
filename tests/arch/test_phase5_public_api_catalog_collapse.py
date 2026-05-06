from __future__ import annotations

from pathlib import Path


def test_app_web_has_no_public_api_or_catalog_modules() -> None:
    for path in Path("app/web").rglob("public_api.py"):
        raise AssertionError(f"unexpected public_api module: {path}")
    for path in Path("app/web").rglob("catalog.py"):
        raise AssertionError(f"unexpected catalog module: {path}")


def test_runtime_platform_support_has_no_public_api_modules() -> None:
    for path in Path("runtime/platform/support").rglob("public_api.py"):
        raise AssertionError(f"unexpected runtime public_api module: {path}")
