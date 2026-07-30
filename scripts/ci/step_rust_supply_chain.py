from __future__ import annotations

import json
import shutil
import subprocess

from scripts.ci.paths import repo_root

ALLOWED_DIRECT_DEPENDENCIES = {"serde", "serde_json"}
ALLOWED_LOCK_PACKAGES = set("businessaios_safety_core itoa memchr proc-macro2 quote serde serde_core serde_derive serde_json syn unicode-ident zmij".split())
FORBIDDEN_MARKERS = set("pyo3 maturin tokio reqwest hyper sqlx diesel rusqlite postgres rand getrandom proptest".split())


def _package_names(text: str) -> set[str]:
    return {line.strip().split('"', 2)[1] for line in text.splitlines() if line.strip().startswith('name = "') and line.strip().endswith('"')}


def _direct_deps(text: str) -> set[str]:
    names: set[str] = set()
    active = False
    for line in text.splitlines():
        item = line.strip()
        if item == "[dependencies]":
            active = True
            continue
        if item.startswith("[") and item.endswith("]"):
            active = False
        if active and item and not item.startswith("#") and "=" in item:
            names.add(item.split("=", 1)[0].strip())
    return names


def _compact(value: object, limit: int = 2000) -> str:
    text = str(value or "").strip().replace("\x00", "")
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def _audit(crate) -> dict[str, object]:
    executable = shutil.which("cargo-audit") or shutil.which("cargo-audit.exe")
    result: dict[str, object] = dict(available=bool(executable), status="unavailable", returncode=None,
                                     failure_kind=None, stdout="", stderr="", report=None)
    if not executable:
        return result
    try:
        completed = subprocess.run([executable, "audit", "--json"], cwd=crate, capture_output=True, text=True, timeout=180)
        try:
            payload = json.loads(completed.stdout) if completed.stdout.strip() else None
        except json.JSONDecodeError:
            payload = None
        result.update(status="passed" if completed.returncode == 0 else "failed", returncode=completed.returncode,
                      stdout=_compact(completed.stdout), stderr=_compact(completed.stderr),
                      report=payload if isinstance(payload, dict) else None)
        if completed.returncode:
            vulnerabilities = payload.get("vulnerabilities", {}) if isinstance(payload, dict) else {}
            warnings = payload.get("warnings", {}) if isinstance(payload, dict) else {}
            if vulnerabilities.get("found") is True or int(vulnerabilities.get("count") or 0) > 0:
                kind = "vulnerabilities_found"
            elif isinstance(warnings, dict) and any(map(bool, warnings.values())):
                kind = "policy_warning"
            elif any(word in completed.stderr.lower() for word in ("network", "failed to fetch", "could not resolve", "connection", "database")):
                kind = "database_or_network_error"
            else:
                kind = "audit_command_failed"
            result["failure_kind"] = kind
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.update(status="failed", failure_kind="tool_error", stderr=_compact(f"{type(exc).__name__}: {exc}"))
    return result


def run() -> tuple[bool, str]:
    root = repo_root()
    crate = root / "rust" / "businessaios_safety_core"
    paths = crate / "Cargo.toml", crate / "Cargo.lock", root / "rust" / "rust-toolchain.toml"
    if not all(path.exists() for path in paths):
        return False, "rust safety supply chain policy files missing"
    cargo_toml, cargo_lock, toolchain = (path.read_text(encoding="utf-8") for path in paths)
    direct_deps, lock_packages = _direct_deps(cargo_toml), _package_names(cargo_lock)
    violations: list[str] = []
    checks = (
        ('channel = "1.75.0"' not in toolchain, "msrv_not_pinned_to_1_75_0"),
        ('edition = "2021"' not in cargo_toml or 'edition = "2024"' in cargo_toml, "rust_edition_policy_violation"),
        ("[dev-dependencies]" in cargo_toml or "[build-dependencies]" in cargo_toml, "dev_or_build_dependencies_forbidden"),
        (direct_deps != ALLOWED_DIRECT_DEPENDENCIES, "direct_dependency_allowlist_violation"),
        (lock_packages != ALLOWED_LOCK_PACKAGES, "lock_package_allowlist_violation"),
    )
    violations.extend(name for failed, name in checks if failed)
    lowered = (cargo_toml + "\n" + cargo_lock).lower()
    violations.extend(f"forbidden_dependency_marker:{item}" for item in sorted(FORBIDDEN_MARKERS) if item in lowered)
    audit = _audit(crate)
    if audit["status"] == "failed":
        violations.append("cargo_audit_failed")
    report = {"artifact": "rust_supply_chain", "passed": not violations, "msrv": "1.75.0", "edition": "2021",
              "direct_dependencies": sorted(direct_deps), "lock_packages": sorted(lock_packages),
              **{f"cargo_audit_{key}": value for key, value in audit.items()}, "violations": violations}
    path = root / "artifacts" / "ci" / "rust_supply_chain.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if violations:
        message = "rust safety supply chain violations: " + ", ".join(violations[:5])
        if "cargo_audit_failed" in violations:
            detail = audit["stderr"] or audit["stdout"] or "no cargo-audit diagnostic output"
            message += f"; cargo_audit_failure_kind={audit['failure_kind'] or 'unknown'}; returncode={audit['returncode']!r}; detail={_compact(detail, 800)}"
        return False, message
    suffix = "cargo-audit unavailable" if audit["status"] == "unavailable" else "cargo-audit passed"
    return True, f"rust safety supply chain diagnostic passed ({suffix}; allowlist policy passed)"


__all__ = ["run"]
