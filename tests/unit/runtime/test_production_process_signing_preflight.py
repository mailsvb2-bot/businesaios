from __future__ import annotations

import pytest

from runtime.bootstrap import process_bootstrap as boot


@pytest.mark.parametrize("missing", ["safety", "simulation"])
def test_production_boot_refuses_missing_signing_secret(monkeypatch, missing):
    for name in ("verify_release_attestation_if_needed",
                 "enforce_production_strict_mode",
                 "enforce_two_admins_in_prod_or_explain",
                 "maybe_disable_singleton_lock_in_dev_test"):
        monkeypatch.setattr(boot, name, lambda: None)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SAFETY_SIGNING_KEYS", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SAFETY_SIGNING_KEYS_JSON", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SAFETY_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SIMULATION_EVIDENCE_SECRET", raising=False)
    if missing == "simulation":
        monkeypatch.setenv("BUSINESAIOS_SAFETY_SIGNING_SECRET", "secure-test-only")
    with pytest.raises((RuntimeError, ValueError), match=(
        "unsafe_policy_signing_key_fallback" if missing == "safety"
        else "simulation_evidence_signing_secret_required"
    )):
        boot._enforce_runtime_process_guards()


def test_development_boot_does_not_require_production_signing_secret(monkeypatch):
    for name in ("verify_release_attestation_if_needed",
                 "enforce_production_strict_mode",
                 "enforce_two_admins_in_prod_or_explain",
                 "maybe_disable_singleton_lock_in_dev_test"):
        monkeypatch.setattr(boot, name, lambda: None)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SAFETY_STRICT_KEYS", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SAFETY_BOOT_STRICT", raising=False)
    boot._enforce_runtime_process_guards()
