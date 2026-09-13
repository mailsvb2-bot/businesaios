#!/usr/bin/env python3
"""Measured BusinessAIOS gates used by ADOS shadow mode.

The bridge composes already-canonical BusinessAIOS CI gates.  It does not
replace the repository CI and it never converts an unsupported assurance into
a PASS.  Unsupported strict gates (notably red_team and dependency_audit) are
left unregistered so ADOS can report UNKNOWN / WOULD_BLOCK honestly.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def isolated_runtime_data_dir() -> Iterator[Path]:
    """Keep every ADOS-measured BusinessAIOS gate out of the source tree.

    ADOS intentionally gives command gates an isolated HOME. BusinessAIOS also
    needs an equally short-lived data root so encrypted key-provider/vault state
    cannot survive the temporary master key or leak between gates.
    """
    previous = {name: os.environ.get(name) for name in ("BUSINESAIOS_DATA_DIR", "DATA_DIR")}
    with tempfile.TemporaryDirectory(prefix="businesaios-ados-gate-data-") as temp_dir:
        runtime_root = Path(temp_dir).resolve()
        try:
            runtime_root.relative_to(ROOT.resolve())
        except ValueError:
            pass
        else:
            raise RuntimeError("ADOS gate runtime data directory must be outside the repository")
        os.environ["BUSINESAIOS_DATA_DIR"] = str(runtime_root)
        os.environ["DATA_DIR"] = str(runtime_root)
        try:
            yield runtime_root
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def run(command: list[str], *, extra_env: dict[str, str] | None = None) -> None:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def canonical_gate(name: str, *, extra_env: dict[str, str] | None = None) -> None:
    run([sys.executable, "-m", "scripts.ci.cli", "--gate", name], extra_env=extra_env)


def pytest(*targets: str) -> None:
    run([sys.executable, "-m", "pytest", "-q", *targets])


def architecture() -> None:
    # BusinessAIOS fast is canonical and contains the architecture-bypass scan,
    # quality check, lock tests, import/boot smoke and regression-impact proof.
    canonical_gate("fast")


def tests() -> None:
    canonical_gate("business-critical")


def security() -> None:
    # Project-level security tests cover keys/vault/signing/PII/secrets.  Rust
    # safety remains a separate canonical project gate and is composed here.
    pytest("tests/security")
    canonical_gate("rust-safety")


def contracts() -> None:
    pytest("tests/contracts")


def integration() -> None:
    canonical_gate("full")


def user_journey() -> None:
    canonical_gate("acceptance")


def data_migration() -> None:
    # The workflow supplies a disposable Postgres service and these flags match
    # the repository's Deep Release migration environment.  Backup/restore proof
    # deliberately remains owned by Deep Release Validation, not by shadow ADOS.
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55432/businesaios"
    )
    env = {
        "DATABASE_URL": database_url,
        "POSTGRES_DSN": os.environ.get("POSTGRES_DSN", database_url),
        "POSTGRES_RUNTIME_ENABLED": "1",
        "POSTGRES_EVENT_STORE_ENABLED": "1",
        "POSTGRES_APPLY_MIGRATIONS": "1",
        "RUN_MIGRATIONS_BEFORE_START": "1",
    }
    canonical_gate("postgres-migrations", extra_env=env)


def full_regression() -> None:
    canonical_gate("full")


def release_disabled() -> None:
    print(
        "ADOS Phase 1 is shadow-only: BusinessAIOS build/release certification is intentionally disabled. "
        "Deep Release Validation and Trusted Production Certification remain authoritative.",
        file=sys.stderr,
    )
    raise SystemExit(78)


HANDLERS = {
    "architecture": architecture,
    "tests": tests,
    "security": security,
    "contracts": contracts,
    "integration": integration,
    "user_journey": user_journey,
    "data_migration": data_migration,
    "full_regression": full_regression,
    "release-disabled": release_disabled,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", choices=sorted(HANDLERS))
    args = parser.parse_args()
    with isolated_runtime_data_dir():
        HANDLERS[args.gate]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
