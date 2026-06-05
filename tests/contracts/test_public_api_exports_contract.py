from __future__ import annotations

import importlib
import json
from pathlib import Path


CONTRACT_PATH = Path("contracts/public_api_exports.json")


def test_public_api_exports_contract() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert int(contract.get("schema_version") or 0) == 1
    exports = contract.get("exports")
    assert isinstance(exports, list)
    assert exports

    missing: list[str] = []
    for entry in exports:
        assert isinstance(entry, dict)
        module_name = str(entry.get("module") or "")
        names = entry.get("names")
        assert module_name
        assert isinstance(names, list)
        module = importlib.import_module(module_name)
        public_all = getattr(module, "__all__", None)
        for name in names:
            public_name = str(name)
            if not hasattr(module, public_name):
                missing.append(f"{module_name}.{public_name}: missing attribute")
                continue
            if public_all is not None and public_name not in public_all:
                missing.append(f"{module_name}.{public_name}: missing from __all__")
    assert not missing, "public API export contract broken:\n" + "\n".join(sorted(missing))
