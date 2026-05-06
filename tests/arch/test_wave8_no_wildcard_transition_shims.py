from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    "runtime/bootstrap/bootstrap_attestation.py",
    "runtime/bootstrap/bootstrap_attestation_store.py",
    "runtime/bootstrap/bootstrap_audit_trail.py",
    "runtime/bootstrap/bootstrap_contract.py",
    "runtime/bootstrap/bootstrap_failfast.py",
    "runtime/bootstrap/bootstrap_lock.py",
    "runtime/bootstrap/entrypoint_manifest.py",
    "runtime/bootstrap/environment_loader.py",
    "runtime/bootstrap/startup_validator.py",
    "runtime/platform/outbox/delivery_state.py",
    "runtime/queue/__init__.py",
]


def test_targeted_transition_shims_use_explicit_exports_only() -> None:
    for rel in TARGETS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "import *" not in text, rel
