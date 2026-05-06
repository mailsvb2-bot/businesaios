from __future__ import annotations

from canon.collapse_readiness import (
    CORE_RUNTIME_COLLAPSED_SURFACES,
    CORE_RUNTIME_COLLAPSE_READY_SURFACES,
)


def test_root_runtime_shims_are_collapsed() -> None:
    expected = {
        "runtime.executor_contract": "runtime.execution.contracts",
        "runtime.read_only_registry": "runtime.application.contracts",
        "runtime.service_exports": "runtime.application.contracts",
        "runtime.capability_access": "runtime.application.contracts",
        "runtime.typed_access": "runtime.application.contracts",
        "runtime.domain_ports": "runtime.application.contracts",
    }
    for source, target in expected.items():
        assert CORE_RUNTIME_COLLAPSED_SURFACES[source] == target
        assert source not in CORE_RUNTIME_COLLAPSE_READY_SURFACES
