from __future__ import annotations

from canon.collapse.architecture_lock_tests import (
    LegacyLockReport,
    assert_no_critical_legacy_findings,
    build_lock_config,
    run_legacy_architecture_locks,
)

__all__ = [
    "LegacyLockReport",
    "assert_no_critical_legacy_findings",
    "build_lock_config",
    "run_legacy_architecture_locks",
]
