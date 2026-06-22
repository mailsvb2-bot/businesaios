from __future__ import annotations

import importlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _physical_route_file_exists(route_module: str) -> bool:
    return (ROOT / Path(*route_module.split(".")).with_suffix(".py")).exists()


def test_runtime_platform_support_import_doors_preserve_registered_synthetic_routes() -> None:
    """Registered synthetic import doors must preserve old public routes.

    This test intentionally skips routes that still have a physical .py file.
    A physical legacy file preserves its own semantics. The import-door law is
    only for routes that were actually collapsed into synthetic modules.
    """

    import runtime.platform.support  # noqa: F401 - installs the import-door finder

    registry_path = ROOT / "runtime/platform/support/import_doors_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    failures: list[str] = []
    checked_routes = 0

    for route_module, exports in sorted(registry.items()):
        if _physical_route_file_exists(route_module):
            continue

        checked_routes += 1

        try:
            route = importlib.import_module(route_module)
        except Exception as exc:  # pragma: no cover - failure detail for CI
            failures.append(f"{route_module}: route import failed: {type(exc).__name__}: {exc}")
            continue

        route_all = set(getattr(route, "__all__", ()))
        expected_exports = set(exports)
        missing_from_all = expected_exports - route_all
        if missing_from_all:
            failures.append(f"{route_module}: missing from __all__: {sorted(missing_from_all)}")

        for export_name, owner_module_name in sorted(exports.items()):
            try:
                owner = importlib.import_module(owner_module_name)
            except Exception as exc:  # pragma: no cover - failure detail for CI
                failures.append(
                    f"{route_module}.{export_name}: owner import failed {owner_module_name}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            if not hasattr(owner, export_name):
                failures.append(f"{route_module}.{export_name}: owner {owner_module_name} lacks export")
                continue
            if not hasattr(route, export_name):
                failures.append(f"{route_module}.{export_name}: route lacks export")
                continue
            if getattr(route, export_name) is not getattr(owner, export_name):
                failures.append(f"{route_module}.{export_name}: route export is not owner export")

    assert checked_routes > 0
    assert failures == []
