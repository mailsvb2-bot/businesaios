from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

from scripts.ci.fs import safe_write_text

PRODUCTION_SYNTHETIC_SCHEMA = "businessaios_production_synthetic_evidence.v1"
PHYSICAL_HARDWARE_SCHEMA = "businessaios_physical_hardware_evidence.v1"
_REQUIRED_PRODUCTION_CHECKS = (
    "production_environment_file", "production_environment", "production_ingress",
    "production_runtime_bindings", "production_credentials", "deployed_sha", "sha_match",
    "service_state", "nginx", "health", "readiness", "runtime", "postgresql",
    "synthetic_flow", "public_api", "public_status",
)


def _read_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON object required: {path}")
    return dict(payload)


def _exact_sha(value: object) -> bool:
    text = str(value or "")
    return len(text) == 40 and text == text.lower() and all(char in "0123456789abcdef" for char in text)


def _base_status(base: Mapping[str, object], exact_sha: str) -> str:
    if base.get("schema") != "businessaios_release_verdict.v1" or base.get("gate") != "release":
        return "FAIL"
    if not _exact_sha(base.get("exact_sha")) or base.get("exact_sha") != exact_sha:
        return "NOT_PROVEN"
    status = str(base.get("status") or "NOT_PROVEN")
    return status if status in {"PASS", "FAIL", "NOT_PROVEN"} else "FAIL"


def production_synthetic_status(evidence: Mapping[str, object], exact_sha: str) -> str:
    if evidence.get("schema") != PRODUCTION_SYNTHETIC_SCHEMA:
        return "FAIL"
    if evidence.get("claims_release_verified") is not False:
        return "FAIL"
    if not _exact_sha(evidence.get("exact_sha")) or evidence.get("exact_sha") != exact_sha:
        return "NOT_PROVEN"
    if evidence.get("observed_sha") != exact_sha:
        return "NOT_PROVEN"
    status = str(evidence.get("status") or "NOT_PROVEN")
    if status != "PASS":
        return status if status in {"FAIL", "NOT_PROVEN"} else "FAIL"
    checks = evidence.get("checks")
    if not isinstance(checks, Mapping) or not evidence.get("synthetic_run_id"):
        return "FAIL"
    for name in _REQUIRED_PRODUCTION_CHECKS:
        item = checks.get(name)
        if not isinstance(item, Mapping) or str(item.get("status") or "").lower() != "pass":
            return "FAIL"
    return "PASS"


def physical_hardware_status(evidence: Mapping[str, object], exact_sha: str) -> str:
    if evidence.get("schema") != PHYSICAL_HARDWARE_SCHEMA or evidence.get("trusted_execution") is not True:
        return "FAIL"
    if not _exact_sha(evidence.get("exact_sha")) or evidence.get("exact_sha") != exact_sha:
        return "NOT_PROVEN"
    if evidence.get("canonical_gate") != "acceptance" or evidence.get("ref") != "refs/heads/main":
        return "FAIL"
    return "PASS" if evidence.get("status") == "PASS" else "FAIL"


def finalize_release_verdict(
    *,
    base_path: Path,
    production_path: Path,
    output_path: Path,
    exact_sha: str,
    hardware_path: Path | None = None,
) -> dict[str, object]:
    if not _exact_sha(exact_sha):
        raise ValueError("exact_sha must be a lowercase 40-character git SHA")
    base = _read_object(base_path)
    production = _read_object(production_path)
    base_state = _base_status(base, exact_sha)
    production_state = production_synthetic_status(production, exact_sha)
    hardware_projection: dict[str, object] = {
        "status": "NOT_PROVEN", "optional": True, "trusted_execution_required": True,
        "artifact": "physical_hardware_evidence.json",
    }
    hardware_state = "PASS"
    if hardware_path is not None:
        hardware = _read_object(hardware_path)
        hardware_state = physical_hardware_status(hardware, exact_sha)
        hardware_projection.update(status=hardware_state, exact_sha=hardware.get("exact_sha"), optional=True)
    states = (base_state, production_state, hardware_state)
    status = "FAIL" if "FAIL" in states else "PASS" if all(state == "PASS" for state in states) else "NOT_PROVEN"
    payload = dict(base)
    payload.update(
        verification_phase="post_deploy",
        status=status,
        production_verified=status == "PASS",
        production_synthetic={
            "status": production_state, "required_for_production": True,
            "artifact": production_path.name, "exact_sha": production.get("exact_sha"),
            "synthetic_run_id": production.get("synthetic_run_id"),
            "source": "scripts/server/verify_runtime_host_contract.sh",
        },
        physical_hardware=hardware_projection,
    )
    safe_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize the canonical release verdict with trusted post-deploy evidence.")
    parser.add_argument("--base-verdict", type=Path, required=True)
    parser.add_argument("--production-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-sha", required=True)
    parser.add_argument("--hardware-evidence", type=Path)
    args = parser.parse_args(argv)
    payload = finalize_release_verdict(
        base_path=args.base_verdict, production_path=args.production_evidence, output_path=args.output,
        exact_sha=args.exact_sha, hardware_path=args.hardware_evidence,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PHYSICAL_HARDWARE_SCHEMA", "PRODUCTION_SYNTHETIC_SCHEMA", "finalize_release_verdict",
    "physical_hardware_status", "production_synthetic_status",
]
