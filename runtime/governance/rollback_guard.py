"""RollbackGuard (canonical term).

Project documents may refer to RollbackGuard.
In code we historically used AutoDeployGuard.
This module provides a stable name + contract to prevent concept drift.
"""

from __future__ import annotations

from runtime.governance.auto_deploy_guard import AutoDeployGuard, build_auto_deploy_guard_from_env

# Canonical alias (same behavior, different term).
RollbackGuard = AutoDeployGuard


def build_rollback_guard_from_env() -> RollbackGuard:
    return build_auto_deploy_guard_from_env()
