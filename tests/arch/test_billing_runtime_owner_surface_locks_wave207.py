from __future__ import annotations

from pathlib import Path

from runtime.canonical_surface_manifest import CANONICAL_PACKAGE_OWNER_SURFACES

ROOT = Path(__file__).resolve().parents[2]


OWNER_FILES = {
    'billing/monetization_adapter.py': ('from runtime.monetization import',),
    'billing/revenue_os_bridge.py': ('from runtime.monetization import',),
    'billing/refund_orchestrator.py': ('from runtime.monetization import', 'from observability.tenant_metrics_registry import'),
    'billing/chargeback_orchestrator.py': ('from runtime.monetization import', 'from observability.tenant_metrics_registry import'),
    'billing/reconciliation_service.py': ('from runtime.monetization import', 'from observability.tenant_metrics_registry import'),
    'billing/scheduler/queue_bridge.py': ('from runtime.queue import',),
    'billing/plan_contract.py': ('from tenancy.tenant_contract import',),
    'billing/quota_policy.py': ('from tenancy.tenant_billing_scope import', 'from tenancy.tenant_contract import'),
    'billing/quota_enforcement.py': ('from tenancy.tenant_quota_guard import', 'from observability.tenant_metrics_registry import'),
}

FORBIDDEN_NESTED_IMPORTS = (
    'from runtime.monetization.contracts import',
    'from runtime.queue.job_',
    'from runtime.queue._',
)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_billing_runtime_owner_surfaces_are_canonical_manifest_entries() -> None:
    for module_name in ('runtime.monetization', 'runtime.queue', 'tenancy', 'observability'):
        assert module_name in CANONICAL_PACKAGE_OWNER_SURFACES


def test_billing_runtime_owner_surfaces_use_package_roots_not_nested_runtime_internals() -> None:
    for relative_path, required_fragments in OWNER_FILES.items():
        text = _read(relative_path)
        for fragment in required_fragments:
            assert fragment in text, f'{relative_path} must depend on canonical owner surface: {fragment}'
        for forbidden in FORBIDDEN_NESTED_IMPORTS:
            assert forbidden not in text, f'{relative_path} must not depend on nested runtime internals: {forbidden}'


def test_billing_runtime_surface_lock_files_exist() -> None:
    for relative_path in (
        'runtime/monetization/__init__.py',
        'runtime/queue/__init__.py',
        'observability/tenant_metrics_registry.py',
        'tenancy/__init__.py',
        'tenancy/tenant_contract.py',
        'tenancy/tenant_billing_scope.py',
        'tenancy/tenant_quota_guard.py',
    ):
        assert (ROOT / relative_path).exists(), f'missing canonical owner surface file: {relative_path}'
