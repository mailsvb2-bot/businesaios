from __future__ import annotations


class ClientMatchEngine:
    """Read-only compatibility facade.

    This helper may expose match previews, but it must never select a final
    business or bypass the canonical demand path.
    """

    def match(self, payload: dict) -> dict:
        row = dict(payload)
        row['mode'] = 'preview_only'
        row['decision_path'] = 'routing_required'
        return {'kind': 'client_match_preview', 'payload': row}
