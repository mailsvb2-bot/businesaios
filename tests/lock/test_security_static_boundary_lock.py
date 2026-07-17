from __future__ import annotations

import ast
from pathlib import Path

from security.secret_vault import SecretEnvelope
from security.secret_vault_backend import (
    SecretEnvelope as CanonicalSecretEnvelope,
)

ROOT = Path(__file__).resolve().parents[2]

SECURITY_FILES = (
    "security/key_provider_sqlite.py",
    "security/secret_vault.py",
    "security/secret_vault_sqlite.py",
    "security/secret_vault_support.py",
)
SAFE_STDLIB_LATE_IMPORTS = {"datetime", "sqlite3"}


def test_secret_envelope_is_static_identity_import() -> None:
    assert SecretEnvelope is CanonicalSecretEnvelope


def test_security_late_imports_are_stdlib_only() -> None:
    violations: list[tuple[str, int, str]] = []

    for relative in SECURITY_FILES:
        path = ROOT / relative
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=relative,
        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "__import__":
                continue
            module = "<dynamic>"
            if (
                node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                module = node.args[0].value
            if module not in SAFE_STDLIB_LATE_IMPORTS:
                violations.append(
                    (relative, int(node.lineno), module)
                )

    assert violations == []
