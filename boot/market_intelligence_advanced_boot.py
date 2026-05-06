from __future__ import annotations

from dataclasses import dataclass, field

from execution.market_intelligence_advanced_pipeline import MarketIntelligenceAdvancedPipeline
from execution.market_intelligence_human_feedback import HumanFeedbackLoop
from execution.market_intelligence_trend_engine import TemporalTrendEngine


CANON_MARKET_INTELLIGENCE_ADVANCED_BOOT = True


@dataclass
class MarketIntelligenceAdvancedRuntime:
    pipeline: MarketIntelligenceAdvancedPipeline = field(default_factory=MarketIntelligenceAdvancedPipeline)
    trend_engine: TemporalTrendEngine = field(default_factory=TemporalTrendEngine)
    feedback_loop: HumanFeedbackLoop = field(default_factory=HumanFeedbackLoop)


def build_market_intelligence_advanced_runtime() -> MarketIntelligenceAdvancedRuntime:
    runtime = MarketIntelligenceAdvancedRuntime()
    runtime.pipeline.trend_engine = runtime.trend_engine
    runtime.pipeline.feedback_loop = runtime.feedback_loop
    return runtime


__all__ = [
    'CANON_MARKET_INTELLIGENCE_ADVANCED_BOOT',
    'MarketIntelligenceAdvancedRuntime',
    'build_market_intelligence_advanced_runtime',
]
