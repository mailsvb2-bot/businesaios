from __future__ import annotations

from core.behavior.operator_catalogs.models import OperatorCatalog


DEFAULT_OPERATOR_CATALOG = OperatorCatalog(
    catalog_id="default",
    phase_gain=1.0,
    anti_drain=0.02,
    event_scales={},
    domain_scales={},
    channel_scales={},
)
