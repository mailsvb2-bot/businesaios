from __future__ import annotations

from collections.abc import Callable
from typing import Any

CANON_BOOT_WIRING_ONLY = True

def boot_with_bundle(*, app: Any, bundle_builder: Callable[..., Any], route_registrar: Callable[..., None], **bundle_kwargs: Any) -> None:
    """Canonical framework-agnostic boot helper.

    Keeps FastAPI/Flask entrypoints as thin boundary adapters while the bundle
    construction path stays single-owner and testable.
    """

    bundle = bundle_builder(**bundle_kwargs)
    route_registrar(app=app, bundle=bundle)
