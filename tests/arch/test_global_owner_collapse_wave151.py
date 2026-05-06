from __future__ import annotations

import importlib
from pathlib import Path


OWNER_PACKAGES = {
    'boot.factories': {
        'build_architecture_watch_service',
        'build_autonomy_advisor_service',
        'build_creative_intelligence_service',
        'build_decision_core',
        'build_decision_gateway',
        'build_runtime_decision_execution_service',
        'build_decision_input_service',
        'build_diffusion_watch_service',
        'build_flow_watch_service',
        'build_governance_chain',
        'build_market_watch_service',
        'build_runtime_packet_provider',
        'build_runtime_state_enrichment_service',
        'build_structure_watch_service',
        'build_world_state_integration_service',
    },
    'boot.registrations': {
        'register_action_budget',
        'register_action_executor',
        'register_architecture_watch',
        'register_autonomy_advisor',
        'register_creative_intelligence',
        'register_decision_core',
        'register_runtime_decision_execution_service',
        'register_decision_gateway',
        'register_decision_input_service',
        'register_diffusion_watch',
        'register_flow_watch',
        'register_governance',
        'register_kill_switch',
        'register_market_watch',
        'register_observability',
        'register_reward',
        'register_risk',
        'register_runtime_packet_provider',
        'register_runtime_state_enrichment',
        'register_simulation',
        'register_structure_watch',
        'register_world_state_integration',
    },
    'core.actions': {'build_catalog', 'build_schema_registry'},
    'execution.effectors': {'build_effector'},
    'marketplace': {'DemandPipeline', 'RequestQuoteFlow', 'process_demand'},
    'observability': {'ExecutionMetrics', 'ExperimentMetrics', 'LeadMetrics', 'PlatformMetrics', 'RevenueMetrics', 'SeoMetrics', 'emit'},
    'config': {
        'BudgetLimits', 'BusinessDefaults', 'ExperimentLimits', 'GravityWeights',
        'RiskThresholds', 'CONFIG_COMPAT_EXPORTS', 'QUALITY_FLOOR',
        'REPUTATION_FLOOR', 'MAX_ROUTING_CANDIDATES', 'MAX_RUNNER_UPS',
    },
}


INTERNAL_OWNER_IMPORTS = {
    'runtime/actions/__init__.py': 'from core.actions import build_schema_registry',
    'runtime/ceo/__init__.py': 'from core.actions import build_schema_registry',
    'execution/effectors/router.py': 'from execution.effectors import build_effector',
    'boot/registrations/__init__.py': '_install_package_alias_modules()',
    'boot/registrations/register_action_executor.py': 'from boot.factories import build_action_executor',
    'observability/revenue_metrics.py': 'from observability import RevenueMetrics as RevenueMetrics',
    'config/business_quality_thresholds.py': 'from config import QUALITY_FLOOR as QUALITY_FLOOR',
}


def test_owner_packages_expose_canonical_exports() -> None:
    for package_name, export_names in OWNER_PACKAGES.items():
        module = importlib.import_module(package_name)
        visible = set(getattr(module, '__all__', ()))
        for export_name in export_names:
            assert hasattr(module, export_name), (package_name, export_name)
            assert export_name in visible, (package_name, export_name)


def test_internal_modules_prefer_owner_surfaces() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for relative_path, expected_import in INTERNAL_OWNER_IMPORTS.items():
        text = (repo_root / relative_path).read_text(encoding='utf-8')
        assert expected_import in text, relative_path
