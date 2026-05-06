from __future__ import annotations

"""Canonical demand components package surface.

Demand card leaf modules have been collapsed into the package owner; historical
module import paths are now provided through centralized alias modules instead
of per-file compat leaves. The historical ``public_api`` import path is also
installed directly by the owner package.
"""

import sys

from runtime.public_api_alias import install_public_api_alias

from app.web.components.demand.renderers import (
    DEMAND_COMPONENT_RENDERERS,
    render_business_quality_card,
    render_lead_delivery_card,
    render_live_demand_feed,
    render_market_balance_card,
    render_revenue_route_card,
    render_routing_reason_card,
)

__all__ = (
    "DEMAND_COMPONENT_RENDERERS",
    "render_business_quality_card",
    "render_lead_delivery_card",
    "render_live_demand_feed",
    "render_market_balance_card",
    "render_revenue_route_card",
    "render_routing_reason_card",
)

for _module_name, _render_name in (
    ("business_quality_card", "render_business_quality_card"),
    ("lead_delivery_card", "render_lead_delivery_card"),
    ("live_demand_feed", "render_live_demand_feed"),
    ("market_balance_card", "render_market_balance_card"),
    ("revenue_route_card", "render_revenue_route_card"),
    ("routing_reason_card", "render_routing_reason_card"),
):
    _module = type(sys)(__name__ + "." + _module_name)
    _module.__package__ = __name__
    _module.__file__ = f"<compat:{__name__}.{_module_name}>"
    _module.__doc__ = f"Compat alias for demand component renderer {_render_name}."
    _module.render = globals()[_render_name]
    _module.__all__ = ["render"]
    sys.modules[_module.__name__] = _module
    setattr(sys.modules[__name__], _module_name, _module)

install_public_api_alias(__name__)
