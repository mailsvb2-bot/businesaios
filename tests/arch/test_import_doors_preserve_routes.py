from __future__ import annotations

import importlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _physical_route_file_exists(route_module: str) -> bool:
    return (ROOT / Path(*route_module.split(".")).with_suffix(".py")).exists()


def _resolve_export(export_name: str, target_spec: str) -> object:
    target_module, separator, target_attr = str(target_spec).partition(":")
    owner = importlib.import_module(target_module)
    return getattr(owner, target_attr or export_name)


def test_runtime_platform_support_import_doors_preserve_registered_synthetic_routes() -> None:
    """Registered synthetic import doors must preserve old public routes.

    Physical legacy .py files keep their own semantics. This law applies to
    routes that are actually collapsed into synthetic import-door modules.
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

        for export_name, target_spec in sorted(exports.items()):
            try:
                expected = _resolve_export(export_name, target_spec)
            except Exception as exc:  # pragma: no cover - failure detail for CI
                failures.append(
                    f"{route_module}.{export_name}: owner resolve failed {target_spec}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            if not hasattr(route, export_name):
                failures.append(f"{route_module}.{export_name}: route lacks export")
                continue
            if getattr(route, export_name) is not expected:
                failures.append(f"{route_module}.{export_name}: route export is not owner export")

    assert checked_routes > 0
    assert failures == []
