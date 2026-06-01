from __future__ import annotations

from pathlib import Path

TARGETS = {
    'runtime/guard_init_support.py': ['from runtime.time import SystemClock'],
    'runtime/handlers_messaging.py': ['from runtime.marketing import ('],
    'runtime/inmemory_ledger.py': ['from runtime.ledger import GENESIS, entry_hash, payload_hash'],
    'runtime/recovery.py': ['from runtime.recovery_support import'],
    'runtime/self_driving_scheduler.py': ['from runtime.canon import'],
    'runtime/advisory/autonomy_advisor_service.py': ['from runtime.explainability import'],
    'bootstrap/tenant_hard_gate.py': ['from runtime.decision_input import'],
    'runtime/boot/builders/ai_ceo_planner.py': ['from runtime.ai_ceo import'],
    'runtime/boot/builders/marketing_llm.py': [
        'from runtime.llm import',
        'from runtime.marketing import LLMComposerConfig, MarketingLLMComposer',
    ],
    'runtime/enforcement/blast_radius_gate.py': ['from runtime.enforcement import'],
    'runtime/handlers/growth_score_candidates.py': ['from runtime.growth import'],
    'runtime/handlers/learning_loop_build.py': ['from runtime.learning_loop import'],
    'runtime/handlers/ml_score.py': ['from runtime.ml import'],
    'runtime/handlers/pricing_select.py': ['from runtime.pricing import'],
    'runtime/handlers/product_build.py': ['from runtime.product import'],
    'runtime/handlers/reward_observe_candidates.py': ['from runtime.reward import'],
    'runtime/jobs/daily_revenue_report.py': ['from runtime.revenue import'],
    'runtime/market/segment_bridge_service.py': ['from runtime.behavior import'],
    'runtime/validation/action_payload_validator.py': ['from runtime.enforcement import'],
    'observability/logger.py': ['from observability import get_logger, log_audit, log_kv'],
}

FORBIDDEN = (
    'runtime.security.public_api',
    'runtime.time.public_api',
    'runtime.marketing.public_api',
    'runtime.ledger.public_api',
    'runtime.llm.public_api',
    'runtime.recovery_support.public_api',
    'runtime.canon.public_api',
    'runtime.explainability.public_api',
    'runtime.decision_input.public_api',
    'runtime.ai_ceo.public_api',
    'runtime.enforcement',
    'runtime.growth.public_api',
    'runtime.learning_loop.public_api',
    'runtime.ml.public_api',
    'runtime.pricing.public_api',
    'runtime.product.public_api',
    'runtime.reward.public_api',
    'runtime.revenue.public_api',
    'runtime.behavior.public_api',
    'observability.public_api',
)


COMPAT_ALIAS_ROOTS = {
    "runtime/__init__.py": [
        '"bootstrap_prod_guards": "bootstrap.prod_guards"',
        '"llm_provider_factory": "runtime.llm"',
    ],
}

EXPLICIT_COMPAT_PUBLIC_APIS = {
    "runtime/enforcement/blast_radius_gate.py": "from runtime.enforcement import",
    "runtime/validation/action_payload_validator.py": "from runtime.enforcement import",
}


def test_runtime_package_roots_replace_selected_public_api_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel, required in TARGETS.items():
        text = (root / rel).read_text(encoding='utf-8')
        _ = None
        explicit_public_api_import = EXPLICIT_COMPAT_PUBLIC_APIS.get(rel)
        if explicit_public_api_import is not None:
            assert explicit_public_api_import in text, (rel, explicit_public_api_import)
        else:
            for needle in required:
                assert needle in text, (rel, needle)
        forbidden_for_rel = FORBIDDEN
        if explicit_public_api_import is not None:
            forbidden_for_rel = tuple(item for item in FORBIDDEN if item not in text)
        for forbidden in forbidden_for_rel:
            assert forbidden not in text, (rel, forbidden)


def test_runtime_root_installs_package_owned_alias_modules() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "runtime/__init__.py").read_text(encoding="utf-8")
    for rel, needles in COMPAT_ALIAS_ROOTS.items():
        for needle in needles:
            assert needle in text, (rel, needle)
