from pathlib import Path

import pytest

from scripts.server import bootstrap_production_control_plane as bootstrap

ROOT = Path(__file__).resolve().parents[2]


def test_production_host_state_contract() -> None:
    expected = bootstrap.CANONICAL_RUNTIME_BINDINGS
    resolved = bootstrap.canonicalize_production_runtime_bindings({"APP_ENV": "prod"})
    assert expected["DATA_DIR"] == resolved["DATA_DIR"] == "/var/lib/businesaios/runtime"
    with pytest.raises(RuntimeError, match="binding mismatch: DATA_DIR"):
        bootstrap.canonicalize_production_runtime_bindings({"DATA_DIR": "/opt/businesaios/data"})
    rewritten = bootstrap._rewrite_managed_assignments(
        "", credential="k", tenant_id="tenant-live", pricing_version="pricing-v1", runtime_bindings=expected
    )
    assert all(f"{key}={value}" in rewritten for key, value in expected.items())
    host = (ROOT / "scripts/server/bootstrap_and_verify_production.sh").read_text()
    assert 'deploy/systemd/dropins/${service}.d/${drop_in_name}' in host
    assert 'cmp -s "$canonical_drop_in" "$drop_in"' in host
    assert "unexpected systemd drop-in" in host
    installer = (ROOT / "deploy/systemd/install.sh").read_text()
    assert 'TELEGRAM_EGRESS_PROFILE="${TELEGRAM_EGRESS_PROFILE:-preserve}"' in installer
    dropin = ROOT / "deploy/systemd/dropins/businesaios-connector-telegram.service.d/20-amsterdam-egress.conf"
    assert "Requires=wg-quick@wg-baios.service" in dropin.read_text()
