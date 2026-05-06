from __future__ import annotations

"""Compatibility surface for ``application.world_state.packet_enrichment``.

This legacy module stays visible because architecture locks still assert the
pure-domain semantics on the historical path during the transition.
"""

from application.world_state.packet_enrichment import (
    CANON_WORLD_STATE_PACKET_ENRICHMENT,
    CANON_WORLD_STATE_PACKET_ENRICHMENT_PURE_DOMAIN,
    build_advisory_notes,
    build_reward_signal_from_world_view,
)

CANON_WORLD_STATE_PACKET_ENRICHMENT = True
CANON_WORLD_STATE_PACKET_ENRICHMENT_PURE_DOMAIN = True

CANON_COMPAT_SHIM = True
CANONICAL_OWNER_MODULE = "application.world_state.packet_enrichment"

__all__ = [
    'CANON_WORLD_STATE_PACKET_ENRICHMENT',
    'CANON_WORLD_STATE_PACKET_ENRICHMENT_PURE_DOMAIN',
    'CANON_COMPAT_SHIM',
    'CANONICAL_OWNER_MODULE',
    'build_advisory_notes',
    'build_reward_signal_from_world_view',
]
