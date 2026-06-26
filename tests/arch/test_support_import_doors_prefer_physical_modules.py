from __future__ import annotations

import importlib
from pathlib import Path


def test_support_import_doors_do_not_shadow_physical_governance_modules() -> None:
    support = importlib.import_module("runtime.platform.support")
    assert support.ARCHITECTURE_NAME

    import_doors = importlib.import_module("runtime.platform.support.import_doors")
    modules = {
        "runtime.platform.support.governance.release_readiness": "ReleaseReadiness",
        "runtime.platform.support.governance.release_policy": "ReleasePolicy",
        "runtime.platform.support.governance.contracts": "AuditWriterContract",
        "runtime.platform.support.governance.audit_writer": "AuditWriter",
    }

    for module_name, export_name in modules.items():
        assert module_name in import_doors.RUNTIME_PLATFORM_SUPPORT_IMPORT_DOORS
        assert import_doors._physical_module_path(module_name) is not None

        module = importlib.import_module(module_name)

        assert hasattr(module, export_name)
        assert module.__loader__.__class__.__name__ != "_RuntimePlatformSupportDoorFinder"
        assert Path(str(module.__file__)).is_absolute()
