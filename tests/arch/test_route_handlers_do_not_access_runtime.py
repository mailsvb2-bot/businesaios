from __future__ import annotations

import importlib
from pathlib import Path


def test_route_handlers_do_not_access_runtime() -> None:
    text = Path("entrypoints/api/route_handlers.py").read_text(encoding="utf-8")

    forbidden = (
        "RuntimeRegistry",
        "ReadOnlyRuntimeRegistry",
        "registry.get(",
        "build_runtime(",
        "RuntimeCapabilityAccess",
    )

    for fragment in forbidden:
        assert fragment not in text
    assert hasattr(importlib.import_module("interfaces.api.route_handlers"), "RouteHandlers")
