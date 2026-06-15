from __future__ import annotations

from canon.canon_ai_enforcer import run_enforcer
from core.ads.hardening.circuit_breaker import AdsCircuitBreaker
from core.causal.builders.event_store_builder import EventCausalBuilder
from core.knowledge.mappers.lesson_deduplicator import LessonDeduplicator
from core.llm import build_anthropic_client
from core.llm.contracts import LLMRequest
from core.strategic_horizon.engine import StrategicMode
from core.strategic_horizon.vector_math import select_horizon

TARGET_PATHS = {
    "core/economics/types.py",
    "core/learning/learning_system.py",
    "core/strategic_horizon/mode_inference.py",
    "core/strategic_horizon/vector_math.py",
    "core/telemetry/behavior_read_model.py",
    "core/telemetry/schemas.py",
    "core/llm/providers/anthropic.py",
    "core/knowledge/mappers/lesson_deduplicator.py",
    "core/finance/strategic/types.py",
    "core/causal/builders/event_store_builder.py",
    "core/causal/estimators/doubly_robust.py",
    "core/behavior/operator_catalogs/models.py",
    "core/ads/hardening/circuit_breaker.py",
}


def test_wave13_hidden_business_logic_paths_are_cleared() -> None:
    report = run_enforcer('.')
    hidden = {v.path for v in report.violations if v.kind == 'hidden-business-logic'}
    assert hidden.isdisjoint(TARGET_PATHS)


def test_wave13_strategic_horizon_policy_surface_stays_canonical() -> None:
    assert select_horizon(StrategicMode.DEFENSE) == 7
    assert select_horizon(StrategicMode.EXPAND) == 45


def test_wave13_anthropic_builder_keeps_defaults() -> None:
    client = build_anthropic_client(
        transport=lambda *_args, **_kwargs: {"content": [{"text": "ok"}], "usage": {"input_tokens": 1, "output_tokens": 2}},
        base_url="https://example.test",
        api_key="k",
        default_model="claude-test",
    )
    out = client.generate_sync(LLMRequest(model="", messages=[]))
    assert out.content == 'ok'
    assert out.usage is not None
    assert out.usage.total_tokens == 3


def test_wave13_deduplicator_threshold_preserved() -> None:
    d = LessonDeduplicator()
    assert d.duplicate_threshold == 0.9


def test_wave13_event_builder_defaults_preserved() -> None:
    builder = EventCausalBuilder()
    assert builder.unit_id_key == 'user_id'


def test_wave13_ads_circuit_breaker_defaults_preserved() -> None:
    breaker = AdsCircuitBreaker()
    assert breaker.can_proceed('meta') is True
