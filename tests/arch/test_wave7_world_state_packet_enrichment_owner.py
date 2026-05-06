from __future__ import annotations

from pathlib import Path


def test_world_state_packet_support_uses_core_packet_enrichment_owner() -> None:
    source = Path("runtime/integration/world_state_packet_support.py").read_text(encoding="utf-8")
    assert "from core.world_state.packet_enrichment import (" in source
    assert "def build_advisory_notes(" not in source
    assert "def build_reward_signal_from_world_view(" not in source


def test_core_packet_enrichment_is_pure_domain_surface() -> None:
    source = Path("core/world_state/packet_enrichment.py").read_text(encoding="utf-8")
    assert "CANON_WORLD_STATE_PACKET_ENRICHMENT = True" in source
    assert "CANON_WORLD_STATE_PACKET_ENRICHMENT_PURE_DOMAIN = True" in source
