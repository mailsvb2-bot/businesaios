from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_runtime_platform_support_import_doors_preserve_registered_routes() -> None:
    """Registered support import doors must behave like the old public modules.

    The expected owner exports are snapshotted before legacy child modules are
    imported. This matters for Python package semantics: importing a child module
    such as ``package.main`` can replace ``package.main`` on the parent package
    with the child module object. That parent-package collision is historical
    Python behavior, not proof that the route lost its export.
    """

    import runtime.platform.support  # noqa: F401 - installs the import-door finder

    registry_path = Path("runtime/platform/support/import_doors_registry.json")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    failures: list[str] = []
    expected: dict[tuple[str, str], object] = {}

    for route_module, exports in sorted(registry.items()):
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

            expected[(route_module, export_name)] = getattr(owner, export_name)

    for route_module, exports in sorted(registry.items()):
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

        for export_name in sorted(exports):
            key = (route_module, export_name)
            if key not in expected:
                continue
            if not hasattr(route, export_name):
                failures.append(f"{route_module}.{export_name}: route lacks export")
                continue
            if getattr(route, export_name) is not expected[key]:
                failures.append(f"{route_module}.{export_name}: route export is not snapshotted owner export")

    assert failures == []
