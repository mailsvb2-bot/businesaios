from __future__ import annotations

"""Canonical demand pages package surface.

Demand page leaf modules have been collapsed into the package owner; historical
module import paths are now provided through centralized alias modules instead
of per-file compat leaves. The historical ``public_api`` import path is also
installed directly by the owner package.
"""

import sys

from runtime.public_api_alias import install_public_api_alias

from app.web.pages.demand.page_loaders import (
    DEMAND_PAGE_LOADERS,
    build_page_loader,
    load_demand_overview,
    load_market_health,
    load_marketplace_settings,
    load_revenue_from_demand,
    load_rows,
)

__all__ = (
    "DEMAND_PAGE_LOADERS",
    "build_page_loader",
    "load_demand_overview",
    "load_market_health",
    "load_marketplace_settings",
    "load_revenue_from_demand",
    "load_rows",
)

for _module_name, _export_name in (
    ("business_quality", "DEMAND_PAGE_LOADERS"),
    ("incoming_demand", "DEMAND_PAGE_LOADERS"),
    ("routing_decisions", "DEMAND_PAGE_LOADERS"),
    ("demand_overview", "load_demand_overview"),
    ("market_health", "load_market_health"),
    ("marketplace_settings", "load_marketplace_settings"),
    ("revenue_from_demand", "load_revenue_from_demand"),
):
    _module = type(sys)(__name__ + "." + _module_name)
    _module.__package__ = __name__
    _module.__file__ = f"<compat:{__name__}.{_module_name}>"
    if _export_name == "DEMAND_PAGE_LOADERS":
        _module.__doc__ = f"Compat alias for demand page loader {_module_name}."
        _module.load = DEMAND_PAGE_LOADERS[_module_name]
        _module.__all__ = ["load"]
    else:
        _module.__doc__ = f"Compat alias for demand page export {_export_name}."
        _module.load = globals()[_export_name]
        _module.__all__ = ["load"]
    sys.modules[_module.__name__] = _module
    setattr(sys.modules[__name__], _module_name, _module)

_page_loader_module = type(sys)(__name__ + ".page_loader")
_page_loader_module.__package__ = __name__
_page_loader_module.__file__ = f"<compat:{__name__}.page_loader>"
_page_loader_module.__doc__ = "Compat alias for demand page loader builder."
_page_loader_module.build_page_loader = build_page_loader
_page_loader_module.__all__ = ["build_page_loader"]
sys.modules[_page_loader_module.__name__] = _page_loader_module
setattr(sys.modules[__name__], "page_loader", _page_loader_module)

_page_rows_module = type(sys)(__name__ + ". _page_rows".replace(" ", ""))
_page_rows_module.__package__ = __name__
_page_rows_module.__file__ = f"<compat:{__name__}._page_rows>"
_page_rows_module.__doc__ = "Compat alias for demand page row loader."
_page_rows_module.load_rows = load_rows
_page_rows_module.__all__ = ["load_rows"]
sys.modules[_page_rows_module.__name__] = _page_rows_module
setattr(sys.modules[__name__], "_page_rows", _page_rows_module)

install_public_api_alias(__name__)
