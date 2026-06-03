from __future__ import annotations

from typing import Any
from collections.abc import Mapping


class ClientOutcomeRequestEnricher:
    """Canonical owner for client-outcome request metadata shaping.

    Keeps enrichment deterministic and side-effect free so the prepared
    execution contract preserves the business/order context without inventing a
    parallel planner.
    """

    def enrich(self, request: Any) -> Any:
        return request

    def enrich_metadata(
        self,
        *,
        existing_metadata: Mapping[str, Any] | None = None,
        order: Any,
    ) -> dict[str, Any]:
        metadata = dict(existing_metadata or {})
        package = getattr(order, 'package', None)
        metadata.setdefault('order_id', getattr(order, 'order_id', ''))
        metadata.setdefault('tenant_id', getattr(order, 'tenant_id', ''))
        metadata.setdefault('business_id', getattr(order, 'business_id', ''))
        if package is not None:
            metadata.setdefault('package_id', getattr(package, 'package_id', ''))
            metadata.setdefault('requested_clients', getattr(package, 'requested_clients', 0))
            metadata.setdefault('attribution_window_days', getattr(package, 'attribution_window_days', 0))
        metadata.setdefault('prepared_contract', True)
        return metadata
