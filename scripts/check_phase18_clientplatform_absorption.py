from __future__ import annotations

import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "config" / "phase18_clientplatform_absorption_manifest.json"
TERMINAL = {"decommissioned", "obsolete"}


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def validate_manifest(data: dict) -> list[str]:
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
        sid = str(item.get("id") or "")
        status = item.get("status")
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


def is_phase18_complete(data: dict) -> bool:
    required = set(data.get("required_donor_capabilities", ()))
    by_id = {item["id"]: item for item in data.get("slices", ())}
    return bool(required) and all(
        by_id.get(capability, {}).get("status") in TERMINAL
        and by_id.get(capability, {}).get("runtime_dependency_removed") is True
        and bool(by_id.get(capability, {}).get("evidence"))
        for capability in required
    )


def main() -> int:
    data = load_manifest()
    errors = validate_manifest(data)
    if errors:
        print("\n".join(errors))
        return 1
    print("phase18 manifest: valid")
    print(f"phase18 complete: {is_phase18_complete(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
