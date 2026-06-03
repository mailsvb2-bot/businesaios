from __future__ import annotations
CANON_BOOT_ROUTE_SURFACE_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True


from types import SimpleNamespace
from typing import Any
from collections.abc import Mapping, MutableMapping


def attach_route_surface(
    app: object,
    *,
    domain: str,
    handlers: Mapping[str, Any] | None = None,
    services: Mapping[str, Any] | None = None,
) -> object:
    key = str(domain)
    attached_handlers = dict(handlers or {})
    attached_services = dict(services or {})

    if isinstance(app, MutableMapping):
        app[f"{key}_handlers"] = attached_handlers
        app[f"{key}_services"] = attached_services
        existing = tuple(app.get("boot_registered_domains", ()))
        if key not in existing:
            app["boot_registered_domains"] = (*existing, key)
        return app

    state = getattr(app, "state", None)
    if state is None:
        state = SimpleNamespace()
        setattr(app, "state", state)
    setattr(state, f"{key}_handlers", attached_handlers)
    setattr(state, f"{key}_services", attached_services)
    existing = tuple(getattr(state, "boot_registered_domains", ()))
    if key not in existing:
        setattr(state, "boot_registered_domains", (*existing, key))
    return app
