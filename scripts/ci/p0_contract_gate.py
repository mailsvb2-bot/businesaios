from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True


@dataclass(frozen=True)
class P0GateResult:
    ok: bool
    failures: tuple[str, ...] = field(default_factory=tuple)


REQUIRED_PATHS = (
    "runtime/wiring.py",
    "runtime/platform/event_store/postgres_event_store.py",
    "interfaces/web/public_site/__init__.py",
    "interfaces/web/public_site/routes.py",
    "application/public_site/service.py",
    "schemas",
    "security",
    "storage",
    "tenancy",
    "execution/effect_evidence.py",
    "scripts/ci/cli.py",
    "pytest.ini",
)

FORBIDDEN_RELEASE_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

FORBIDDEN_FILE_SUFFIXES = (".bak", ".tmp", "~")


def run_p0_contract_gate(root: Path) -> P0GateResult:
    failures: list[str] = []
    for rel in REQUIRED_PATHS:
        if not (root / rel).exists():
            failures.append(f"missing required P0 path: {rel}")

    for path in root.rglob("*"):
        rel_path = path.relative_to(root)
        rel = rel_path.as_posix()
        if set(rel_path.parts).intersection(FORBIDDEN_RELEASE_DIRS):
            failures.append(f"forbidden release artifact: {rel}")
            if len(failures) > 100:
                break
        if path.is_file() and path.name.endswith(FORBIDDEN_FILE_SUFFIXES):
            failures.append(f"forbidden backup/temp file: {rel}")

    return P0GateResult(ok=not failures, failures=tuple(failures))


def main() -> int:
    root = Path.cwd()
    result = run_p0_contract_gate(root)
    if result.ok:
        print("p0_contract_gate: OK")
        return 0
    print("p0_contract_gate: FAILED")
    for failure in result.failures[:100]:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
