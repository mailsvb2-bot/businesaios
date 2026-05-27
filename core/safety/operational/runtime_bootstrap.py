from __future__ import annotations

import os
from pathlib import Path

from core.safety.operational.factory import (
    OperationalSafetyRuntime,
    build_persistent_operational_safety_runtime,
)
from core.safety.operational.tenant_policy_provider import TenantOperationalBudgetPolicyProvider

CANON_OPERATIONAL_RUNTIME_BOOTSTRAP = True


def resolve_operational_safety_runtime(*, default_root: str | Path = '.runtime') -> OperationalSafetyRuntime:
    root = Path(default_root)
    ledger_path = Path(
        os.environ.get('BUSINESAIOS_OPERATIONAL_BUDGET_LEDGER')
        or (root / 'operational_budget' / 'ledger.json')
    )
    policy_path = os.environ.get('BUSINESAIOS_OPERATIONAL_BUDGET_POLICY_JSON')
    policy_provider = None
    if str(policy_path or '').strip():
        policy_provider = TenantOperationalBudgetPolicyProvider.from_json_file(str(policy_path))
    return build_persistent_operational_safety_runtime(
        storage_path=ledger_path,
        policy_provider=policy_provider,
    )


__all__ = [
    'CANON_OPERATIONAL_RUNTIME_BOOTSTRAP',
    'resolve_operational_safety_runtime',
]
