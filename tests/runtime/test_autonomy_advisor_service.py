from __future__ import annotations

from core.creative_intelligence.models import (
    CreativeIntelligenceSnapshot,
    CreativePnLSnapshot,
    ExperimentConfidenceSnapshot,
    IncrementalitySnapshot,
)
from runtime.advisory.autonomy_advisor_service import AutonomyAdvisorService
from runtime.audit_log import RuntimeAuditLog
from runtime.market.market_snapshot import MarketSnapshot
from runtime.runtime_observability import RuntimeObservability


def test_autonomy_advisor_builds_advisory_packet() -> None:
    service = AutonomyAdvisorService(
        observability=RuntimeObservability(audit_log=RuntimeAuditLog()),
    )
    packet = service.build_packet(
        market_snapshot=MarketSnapshot(
            global_macro_score=0.6,
            global_micro_score=0.5,
            global_competitive_shift=0.2,
            segment_states=(),
        ),
        ranked_creatives=(
            CreativeIntelligenceSnapshot(
                creative_id="c1",
                pnl=CreativePnLSnapshot("c1", 300.0, 200.0, 100.0, 0.33, 0.5),
                incrementality=IncrementalitySnapshot("c1", 0.2, 0.8, 0.2, "dr"),
                experiment_confidence=ExperimentConfidenceSnapshot("c1", 0.1, 0.03, 0.97, 0.75),
                expected_value_score=0.4,
                downside_envelope=0.2,
                portfolio_rank_score=0.5,
                explanations=(),
            ),
        ),
        architecture_global_stability=0.8,
        flow_turbulence=0.2,
    )
    assert packet.packet_name == "autonomy_advisory_v1"
    assert len(packet.recommendations) == 1
