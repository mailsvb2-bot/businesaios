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
            owner = str(item.get("canonical_owner") or "")
            if not owner:
                errors.append(f"{sid}: canonical_owner required for {status}")
            if "clientplatform" in owner.casefold():
                errors.append(f"{sid}: donor-specific canonical_owner is forbidden")
            if not item.get("source_of_truth"):
                errors.append(f"{sid}: source_of_truth required for {status}")
        if status in {"parity_proven", "cutover", "decommissioned"} and not item.get("evidence"):
            errors.append(f"{sid}: evidence required for {status}")
        if status in {"cutover", "decommissioned"} and not item.get("runtime_dependency_removed"):
            errors.append(f"{sid}: runtime dependency must be removed before {status}")
    return errors


def _complete(data: dict) -> bool:
    # The original 20 donor capabilities are a FLOOR, not the full product.
    # Every newly inventoried user-visible extension must also be resolved
    # before ClientPlatform can be shut down without capability loss.
    slices = tuple(data.get("slices", ()))
    return bool(data.get("required_donor_capabilities")) and bool(slices) and not _validate(data) and all(
        item.get("status") in TERMINAL
        and item.get("runtime_dependency_removed") is True
        and bool(item.get("evidence"))
        for item in slices
    )


def test_phase18_absorption_manifest_is_valid_but_not_falsely_complete() -> None:
    data = _manifest()
    assert not _validate(data)
    unresolved = any(
        item.get("status") not in TERMINAL
        or item.get("runtime_dependency_removed") is not True
        or not item.get("evidence")
        for item in data["slices"]
    )
    assert _complete(data) is (not unresolved)


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


def test_phase18_growth_policy_allows_useful_code_but_not_parallel_runtime() -> None:
    ledger = json.loads((ROOT / "canon" / "metrics_debt_ledger.json").read_text(encoding="utf-8"))
    policy = ledger["phase18_absorption_growth_policy"]
    assert policy["active"] is True
    assert policy["donor_repository"] == "mailsvb2-bot/clientplatform"
    assert policy["target_product"] == "BusinessAIOS"
    assert int(policy["python_line_budget"]) > 0
    assert int(policy["python_file_budget"]) > 0
    assert int(policy["transition_surface_budget"]) == 0
    assert policy["donor_runtime_imports_allowed"] is False
    assert policy["parallel_owners_allowed"] is False
    assert policy["duplicate_runtimes_allowed"] is False


def test_phase18_does_not_create_donor_named_python_runtime_surfaces() -> None:
    offenders = []
    for root_name in RUNTIME_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        offenders.extend(
            str(path.relative_to(ROOT))
            for path in root.rglob("*.py")
            if "clientplatform" in path.relative_to(ROOT).as_posix().casefold()
        )
    assert not offenders, "\n".join(offenders)



def test_phase18_completion_includes_new_user_visible_extension_slices() -> None:
    original = _manifest()
    donor_floor = set(original["required_donor_capabilities"])
    extensions = [item["id"] for item in original["slices"] if item["id"] not in donor_floor]
    assert extensions, "phase18 needs to account for donor features discovered after the baseline"
    # Construct an otherwise valid, fully migrated manifest; do not confuse
    # synthetic contract validation with real production-cutover evidence.
    ready = {
        **original,
        "slices": [
            {
                **item,
                "status": "decommissioned",
                "canonical_owner": item.get("canonical_owner") or "canonical.owner",
                "source_of_truth": item.get("source_of_truth") or "canonical Event Store",
                "evidence": ["synthetic-test-evidence"],
                "runtime_dependency_removed": True,
            }
            for item in original["slices"]
        ],
    }
    assert not _validate(ready)
    assert _complete(ready) is True

    extension = next(item for item in ready["slices"] if item["id"] == extensions[0])
    extension["status"] = "implemented"
    assert _complete(ready) is False, "a non-baseline UI/UX journey blocks donor shutdown"
    extension["status"] = "decommissioned"

    ready["slices"].append({**extension})
    assert _complete(ready) is False, "duplicate slice IDs must never count as done"
