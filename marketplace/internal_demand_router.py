from __future__ import annotations


class InternalDemandRouter:
    """Compatibility facade.

    This module must never emit executable routing decisions. It can only pass
    preview payloads downstream to the canonical demand flow.
    """

    def route(self, payload: dict) -> dict:
        row = dict(payload)
        row['mode'] = 'preview_only'
        row['decision_path'] = 'routing_required'
        return {'kind': 'internal_demand_route_preview', 'payload': row}
