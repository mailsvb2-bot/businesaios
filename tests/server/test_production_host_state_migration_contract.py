from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.server import bootstrap_production_control_plane as bootstrap


ROOT = Path(__file__).resolve().parents[2]
HOST_LIFECYCLE = ROOT / "scripts" / "server" / "bootstrap_and_verify_production.sh"
SYSTEMD_INSTALLER = ROOT / "deploy" / "systemd" / "install.sh"
AMSTERDAM_DROPIN = (
    ROOT
    / "deploy"
    / "systemd"
    / "dropins"
    / "businesaios-connector-telegram.service.d"
    / "20-amsterdam-egress.conf"
)


def test_canonical_runtime_bindings_fill_legacy_gaps_without_becoming_operator_input() -> None:
    expected = {
        "PRODUCTION_STRICT_MODE": "1",
        "DATA_DIR": "/var/lib/businesaios/runtime",
        "PRICING_FINGERPRINT_PATH": "/var/lib/businesaios/runtime/governance/pricing_fingerprint.json",
        "BUSINESAIOS_TENANT_REGISTRY_BACKEND": "file",
        "BUSINESAIOS_TENANT_REGISTRY_PATH": "/var/lib/businesaios/runtime/tenancy/tenant_registry.json",
        "BUSINESAIOS_TENANT_POLICY_STORE_BACKEND": "file",
        "BUSINESAIOS_TENANT_POLICY_STORE_PATH": "/var/lib/businesaios/runtime/tenancy/tenant_policies.json",
    }
    assert bootstrap.CANONICAL_RUNTIME_BINDINGS == expected

    source = {
        "APP_ENV": "prod",
        "PUBLIC_BASE_URL": "https://api.businessaios.ru",
    }
    resolved = bootstrap.canonicalize_production_runtime_bindings(source)
    assert resolved["APP_ENV"] == "prod"
    assert resolved["PUBLIC_BASE_URL"] == "https://api.businessaios.ru"
    for key, value in expected.items():
        assert resolved[key] == value


def test_canonical_runtime_bindings_reject_conflicting_host_state() -> None:
    with pytest.raises(RuntimeError, match="canonical production binding mismatch: DATA_DIR"):
        bootstrap.canonicalize_production_runtime_bindings(
            {"DATA_DIR": "/opt/businesaios/data"}
        )


def test_atomic_env_rewrite_binds_runtime_tenant_pricing_and_credential_together() -> None:
    original = "APP_ENV=prod\nUNRELATED_SECRET=preserve-me\n"
    rewritten = bootstrap._rewrite_managed_assignments(
        original,
        credential="key.secret",
        tenant_id="tenant-live",
        pricing_version="pricing-2026-08",
        runtime_bindings=bootstrap.CANONICAL_RUNTIME_BINDINGS,
    )
    assert "UNRELATED_SECRET=preserve-me" in rewritten
    assert "CONTROL_PLANE_API_KEY=key.secret" in rewritten
    assert "SMOKE_TENANT_ID=tenant-live" in rewritten
    assert "PRICING_VERSION=pricing-2026-08" in rewritten
    for key, value in bootstrap.CANONICAL_RUNTIME_BINDINGS.items():
        assert f"{key}={value}" in rewritten


def test_host_lifecycle_accepts_only_release_declared_byte_identical_dropins() -> None:
    subprocess.run(["bash", "-n", str(HOST_LIFECYCLE)], check=True)
    text = HOST_LIFECYCLE.read_text(encoding="utf-8")
    assert "canonicalize_production_runtime_bindings" in text
    assert 'deploy/systemd/dropins/${service}.d/${drop_in_name}' in text
    assert 'cmp -s "$canonical_drop_in" "$drop_in"' in text
    assert "unexpected systemd drop-in for $service" in text
    assert "installed systemd drop-in does not match deployed SHA" in text


def test_systemd_installer_has_explicit_preserve_amsterdam_direct_egress_profiles() -> None:
    subprocess.run(["bash", "-n", str(SYSTEMD_INSTALLER)], check=True)
    text = SYSTEMD_INSTALLER.read_text(encoding="utf-8")
    assert 'TELEGRAM_EGRESS_PROFILE="${TELEGRAM_EGRESS_PROFILE:-preserve}"' in text
    assert 'preserve|amsterdam|direct' in text
    assert "TELEGRAM_EGRESS_PROFILE=amsterdam requires ENABLE_TELEGRAM_CONNECTOR=1" in text
    assert 'install -m 0644 "$TELEGRAM_AMSTERDAM_DROPIN_SOURCE" "$TELEGRAM_AMSTERDAM_DROPIN_TARGET"' in text
    assert 'rm -f "$TELEGRAM_AMSTERDAM_DROPIN_TARGET"' in text
    assert "telegram_egress_profile" in text


def test_amsterdam_telegram_egress_profile_is_versioned_exactly() -> None:
    assert AMSTERDAM_DROPIN.read_text(encoding="utf-8") == (
        "[Unit]\n"
        "Requires=wg-quick@wg-baios.service\n"
        "After=wg-quick@wg-baios.service\n"
        "After=network-online.target\n"
    )
