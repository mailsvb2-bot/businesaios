from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config" / "phase18_clientplatform_absorption_manifest.json"
TERMINAL = {"decommissioned", "obsolete"}
RUNTIME_ROOTS = (
    "application", "billing", "core", "crm", "execution",
    "governance", "interfaces", "runtime",
)


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _validate(data: dict) -> list[str]:
    errors: list[str] = []
    required = set(data.get("required_donor_capabilities", ()))
    slices = data.get("slices", ())
    ids = [item.get("id") for item in slices]
    if len(ids) != len(set(ids)):
        errors.append("duplicate phase18 slice id")
    missing = required - set(ids)
    if missing:
        errors.append("missing donor capabilities: " + ", ".join(sorted(missing)))
    allowed = set(data.get("allowed_statuses", ()))
    for item in slices:
        sid, status = str(item.get("id") or ""), item.get("status")
        if status not in allowed:
            errors.append(f"{sid}: invalid status {status!r}")
        if status in {"mapped", "implemented", "parity_proven", "cutover", "decommissioned"}:
            if not item.get("canonical_owner"):
                errors.append(f"{sid}: canonical_owner required for {status}")
            if not item.get("source_of_truth"):
                errors.append(f"{sid}: source_of_truth required for {status}")
        if status in {"parity_proven", "cutover", "decommissioned"} and not item.get("evidence"):
            errors.append(f"{sid}: evidence required for {status}")
        if status in {"cutover", "decommissioned"} and not item.get("runtime_dependency_removed"):
            errors.append(f"{sid}: runtime dependency must be removed before {status}")
    return errors


def _complete(data: dict) -> bool:
    required = set(data.get("required_donor_capabilities", ()))
    by_id = {item["id"]: item for item in data.get("slices", ())}
    return bool(required) and all(
        by_id.get(capability, {}).get("status") in TERMINAL
        and by_id.get(capability, {}).get("runtime_dependency_removed") is True
        and bool(by_id.get(capability, {}).get("evidence"))
        for capability in required
    )


def test_phase18_absorption_manifest_is_valid_but_not_falsely_complete() -> None:
    data = _manifest()
    assert not _validate(data)
    assert _complete(data) is False


def test_businessaios_runtime_has_no_clientplatform_import_dependency() -> None:
    violations: list[str] = []
    for root_name in RUNTIME_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("clientplatform"):
                    violations.append(f"{path.relative_to(ROOT)} imports {node.module}")
                elif isinstance(node, ast.Import):
                    violations.extend(
                        f"{path.relative_to(ROOT)} imports {alias.name}"
                        for alias in node.names
                        if alias.name.startswith("clientplatform")
                    )
    assert not violations, "\n".join(violations)
