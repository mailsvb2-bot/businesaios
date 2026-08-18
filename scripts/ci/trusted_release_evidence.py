from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.ci.fs import safe_write_text

CANON_TRUSTED_RELEASE_EVIDENCE_ADAPTER = True
PRODUCTION_SYNTHETIC_SCHEMA = "businessaios_production_synthetic_evidence.v1"
PHYSICAL_HARDWARE_SCHEMA = "businessaios_physical_hardware_evidence.v1"
RELEASE_VERDICT_SCHEMA = "businessaios_release_verdict.v1"
_REQUIRED_PRODUCTION_CHECKS = (
    "canonical_python",
    "production_environment_file",
    "production_environment",
    "production_ingress",
    "production_runtime_bindings",
    "production_credentials",
    "deployed_sha",
    "sha_match",
    "service_state",
    "nginx",
    "health",
    "readiness",
    "runtime",
    "postgresql",
    "synthetic_flow",
    "public_api",
    "public_status",
)


class TrustedEvidenceError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TrustedEvidenceError(f"invalid or missing evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise TrustedEvidenceError(f"evidence must be a JSON object: {path}")
    return payload


def _write(path: Path, payload: dict[str, object]) -> None:
    safe_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _exact_sha(value: object) -> str | None:
    text = str(value or "")
    return (
        text
        if len(text) == 40
        and text == text.lower()
        and all(ch in "0123456789abcdef" for ch in text)
        else None
    )


def _check_passed(checks: dict[str, object], name: str) -> bool:
    item = checks.get(name)
    return isinstance(item, dict) and str(item.get("status") or "").lower() == "pass"


def _production_proof(
    evidence: dict[str, object], exact_sha: str
) -> dict[str, object]:
    raw_checks = evidence.get("checks")
    checks = raw_checks if isinstance(raw_checks, dict) else {}
    missing = [
        name for name in _REQUIRED_PRODUCTION_CHECKS if not _check_passed(checks, name)
    ]
    violations: list[str] = []
    if evidence.get("schema") != PRODUCTION_SYNTHETIC_SCHEMA:
        violations.append("production_synthetic_schema_invalid")
    if evidence.get("status") != "PASS":
        violations.append("production_synthetic_status_not_pass")
    if (
        _exact_sha(evidence.get("exact_sha")) != exact_sha
        or _exact_sha(evidence.get("observed_sha")) != exact_sha
    ):
        violations.append("production_synthetic_exact_sha_mismatch")
    if str(evidence.get("environment") or "").lower() not in {"prod", "production"}:
        violations.append("production_synthetic_environment_invalid")
    if (
        not str(evidence.get("tenant_id") or "").strip()
        or evidence.get("tenant_id") == "default-business"
    ):
        violations.append("production_synthetic_tenant_invalid")
    if not str(evidence.get("synthetic_run_id") or "").strip():
        violations.append("production_synthetic_run_id_missing")
    if missing:
        violations.append("production_synthetic_checks_not_pass:" + ",".join(missing))
    if evidence.get("claims_production_ready") is not False:
        violations.append("production_synthetic_must_not_claim_release_ready")
    if not violations:
        status = "PASS"
    elif violations == ["production_synthetic_exact_sha_mismatch"]:
        status = "NOT_PROVEN"
    else:
        status = "FAIL"
    return {
        "status": status,
        "schema": evidence.get("schema"),
        "exact_sha": evidence.get("exact_sha"),
        "observed_sha": evidence.get("observed_sha"),
        "synthetic_run_id": evidence.get("synthetic_run_id"),
        "tenant_id": evidence.get("tenant_id"),
        "required_checks": list(_REQUIRED_PRODUCTION_CHECKS),
        "violations": violations,
        "source": "trusted-production-post-deploy-evidence",
    }


def _physical_proof(
    evidence: dict[str, object] | None, exact_sha: str
) -> dict[str, object]:
    if evidence is None:
        return {
            "status": "NOT_PROVEN",
            "optional": True,
            "violations": ["physical_hardware_evidence_absent"],
        }
    violations: list[str] = []
    if evidence.get("schema") != PHYSICAL_HARDWARE_SCHEMA:
        violations.append("physical_hardware_schema_invalid")
    if evidence.get("status") != "PASS":
        violations.append("physical_hardware_status_not_pass")
    if _exact_sha(evidence.get("exact_sha")) != exact_sha:
        violations.append("physical_hardware_exact_sha_mismatch")
    if str(evidence.get("platform") or "").lower() != "windows":
        violations.append("physical_hardware_platform_not_windows")
    if evidence.get("acceptance_gate") != "PASS":
        violations.append("physical_hardware_acceptance_not_pass")
    return {
        "status": "PASS" if not violations else "FAIL",
        "optional": True,
        "violations": violations,
        "exact_sha": evidence.get("exact_sha"),
        "platform": evidence.get("platform"),
        "runner": evidence.get("runner"),
        "acceptance_gate": evidence.get("acceptance_gate"),
    }


def finalize_trusted_release_verdict(
    *,
    base_verdict_path: Path,
    production_evidence_path: Path,
    output_path: Path,
    physical_evidence_path: Path | None = None,
    require_physical_hardware: bool = False,
) -> dict[str, object]:
    base = _load(base_verdict_path)
    exact_sha = _exact_sha(base.get("exact_sha"))
    if (
        base.get("schema") != RELEASE_VERDICT_SCHEMA
        or base.get("gate") != "release"
        or exact_sha is None
    ):
        raise TrustedEvidenceError(
            "base artifact is not an exact-SHA canonical release verdict"
        )
    if base.get("status") != "PASS":
        raise TrustedEvidenceError(
            f"base canonical release verdict is not PASS: {base.get('status')!r}"
        )

    production = _production_proof(_load(production_evidence_path), exact_sha)
    physical = _physical_proof(
        _load(physical_evidence_path) if physical_evidence_path else None,
        exact_sha,
    )
    states = [str(production["status"])]
    if require_physical_hardware:
        states.append(str(physical["status"]))
    status = (
        "FAIL"
        if "FAIL" in states
        else "PASS" if all(item == "PASS" for item in states) else "NOT_PROVEN"
    )

    payload = dict(base)
    payload.update(
        status=status,
        scope=str(base.get("scope") or "") + "-and-wave-f-trusted-production-proof",
        certification_profile="wave_f_trusted",
        production_synthetic=production,
        physical_hardware=physical,
        trusted_evidence={
            "status": status,
            "physical_hardware_required": require_physical_hardware,
        },
    )
    _write(output_path, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-verdict", type=Path, required=True)
    parser.add_argument("--production-evidence", type=Path, required=True)
    parser.add_argument("--physical-evidence", type=Path)
    parser.add_argument("--require-physical-hardware", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload = finalize_trusted_release_verdict(
            base_verdict_path=args.base_verdict,
            production_evidence_path=args.production_evidence,
            physical_evidence_path=args.physical_evidence,
            require_physical_hardware=bool(args.require_physical_hardware),
            output_path=args.output,
        )
    except TrustedEvidenceError as exc:
        print(f"[trusted-release-evidence] blocked: {exc}")
        return 2
    print(
        f"[trusted-release-evidence] status={payload['status']} "
        f"exact_sha={payload['exact_sha']}"
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CANON_TRUSTED_RELEASE_EVIDENCE_ADAPTER",
    "TrustedEvidenceError",
    "finalize_trusted_release_verdict",
]
