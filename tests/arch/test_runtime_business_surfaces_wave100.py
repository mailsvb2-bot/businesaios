from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_IMPORTS = {
    'runtime/advisory/autonomy_advisor_service.py': (
        'from core.creative_intelligence',
        'from core.explainability',
        'from core.decisioning.decision_output_guard',
    ),
    'runtime/creative/creative_intelligence_service.py': (
        'from core.creative_intelligence',
        'from core.scorers.portfolio',
    ),
    'runtime/integration/world_state_integration_service.py': (
        'from core.creative_intelligence',
        'from core.explainability',
    ),
    'runtime/handlers/economics_build.py': (
        'from core.economics',
    ),
    'runtime/handlers/economics_explain.py': (
        'from core.economics',
    ),
    'runtime/handlers/economics_score_candidates.py': (
        'from core.economics',
    ),
    'runtime/boot/builders/ai_ceo_planner.py': (
        'from core.ai_ceo',
    ),
    'runtime/handlers/ai_ceo_plan.py': (
        'from core.ai_ceo',
    ),
    'runtime/handlers/ads_autopilot/request_builder.py': (
        'from core.economics.objective',
    ),
}

REQUIRED_IMPORTS = {
    'runtime/advisory/autonomy_advisor_service.py': (
        'from runtime.creative import CreativeIntelligenceSnapshot',
        'from runtime.explainability import assert_non_decision_payload, build_creative_reasons, to_lines',
    ),
    'runtime/creative/creative_intelligence_service.py': (
        'from runtime.creative import (',
    ),
    'runtime/integration/world_state_integration_service.py': (
        'from runtime.creative import CreativeIntelligenceSnapshot',
    ),
    'runtime/handlers/economics_build.py': (
        'from runtime.economics import BudgetEnvelope, UnitEconomicsSnapshot, build_budget_envelope',
    ),
    'runtime/handlers/economics_explain.py': (
        'from runtime.economics import UnitEconomicsSnapshot, explain_unit_economics',
    ),
    'runtime/handlers/economics_score_candidates.py': (
        'from runtime.economics import EconomicsScoringContext, EconomicsService',
    ),
    'runtime/boot/builders/ai_ceo_planner.py': (
        'from runtime.ai_ceo import (',
    ),
    'runtime/handlers/ai_ceo_plan.py': (
        'from runtime.ai_ceo import render_plan_text',
    ),
    'runtime/handlers/ads_autopilot/request_builder.py': (
        'from runtime.economics import normalize_objective',
    ),
}


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding='utf-8')


def test_runtime_business_surfaces_do_not_import_core_directly() -> None:
    for rel_path, patterns in FORBIDDEN_IMPORTS.items():
        text = _read(rel_path)
        for pattern in patterns:
            assert pattern not in text, f'{rel_path} must not import {pattern} directly'


def test_runtime_business_surfaces_use_public_apis() -> None:
    for rel_path, patterns in REQUIRED_IMPORTS.items():
        text = _read(rel_path)
        for pattern in patterns:
            assert pattern in text, f'{rel_path} must import via runtime public surface: {pattern}'
