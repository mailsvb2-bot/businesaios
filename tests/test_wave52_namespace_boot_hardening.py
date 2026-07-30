from __future__ import annotations

from boot.runtime_boot_manifest import RUNTIME_BOOT_MANIFEST
from runtime.service_names import RuntimeServiceName
from canon.namespace_aliases import CANONICAL_NAMESPACE_ALIASES, canonical_namespace_for


def test_namespace_aliases_point_to_canonical_targets():
    assert CANONICAL_NAMESPACE_ALIASES["core.products"] == "core.product"
    assert CANONICAL_NAMESPACE_ALIASES["core.decision"] == "core.decisioning"
    assert canonical_namespace_for("core.learning") == "core.learning_loop"
    assert canonical_namespace_for("core.product") == "core.product"


def test_runtime_boot_manifest_has_single_decision_execution_step():
    names = [entry.service_name for entry in RUNTIME_BOOT_MANIFEST]
    callables = [entry.callable_name for entry in RUNTIME_BOOT_MANIFEST]
    assert names.count(RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE) == 1
    assert names.count(RuntimeServiceName.DECISION_CORE) == 0
    assert callables.count("register_decision_core") == 1
    assert names.count(RuntimeServiceName.DECISION_GATEWAY) == 1
