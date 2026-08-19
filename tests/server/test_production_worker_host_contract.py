from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_LIFECYCLE = PROJECT_ROOT / "scripts" / "server" / "bootstrap_and_verify_production.sh"
WORKER_UNIT = PROJECT_ROOT / "deploy" / "systemd" / "businesaios-worker.service"
PRODUCTION_ENV_TEMPLATE = PROJECT_ROOT / ".env.example.prod"


def test_host_lifecycle_preflights_worker_bind_before_credential_mutation() -> None:
    subprocess.run(["bash", "-n", str(HOST_LIFECYCLE)], check=True)
    text = HOST_LIFECYCLE.read_text(encoding="utf-8")

    assert '"HEALTH_HOST": "127.0.0.1"' in text
    assert '"WORKER_HEALTH_PORT": "8087"' in text
    assert '"EVOLUTION_HEALTH_PORT": "8087"' in text
    assert 'EVOLUTION_ENABLED must be enabled in canonical production' in text
    assert text.index("== canonical production runtime preflight ==") < text.index(
        "== canonical production control-plane + pricing bootstrap =="
    )
    assert '--tenant-id "$SMOKE_TENANT"' in text
    assert '--pricing-version "$APPROVED_PRICING_VERSION"' in text
    assert 'NeedDaemonReload --value' in text
    assert 'DropInPaths --value' in text
    assert "systemd manager state is stale" in text
    assert "unexpected systemd drop-ins" in text
    assert "installed systemd unit does not match deployed SHA" in text


def test_host_lifecycle_restarts_and_waits_for_both_core_services() -> None:
    text = HOST_LIFECYCLE.read_text(encoding="utf-8")

    assert 'WORKER_SERVICE="businesaios-worker.service"' in text
    assert 'LOCAL_WORKER_HEALTH_URL="http://127.0.0.1:8087/health"' in text
    assert 'LOCAL_WORKER_READINESS_URL="http://127.0.0.1:8087/ready"' in text
    assert 'systemctl restart "$API_SERVICE" "$WORKER_SERVICE"' in text
    assert 'systemctl is-active --quiet "$WORKER_SERVICE"' in text
    assert 'curl -fsS --max-time 2 "$LOCAL_WORKER_HEALTH_URL"' in text
    assert 'curl -fsS --max-time 2 "$LOCAL_WORKER_READINESS_URL"' in text
    assert "timeout 60s bash -c" in text


def test_systemd_worker_pins_health_surface_to_loopback_even_if_env_drifts() -> None:
    text = WORKER_UNIT.read_text(encoding="utf-8")
    exec_start = next(line for line in text.splitlines() if line.startswith("ExecStart="))

    assert "APP_PROFILE=worker" in exec_start
    assert "HEALTH_HOST=127.0.0.1" in exec_start
    assert "WORKER_HEALTH_PORT=8087" in exec_start
    assert "EVOLUTION_HEALTH_PORT=8087" in exec_start
    assert "EVOLUTION_ENABLED=1" in exec_start


def test_production_template_matches_loopback_worker_contract() -> None:
    text = PRODUCTION_ENV_TEMPLATE.read_text(encoding="utf-8")

    assert "HEALTH_HOST=127.0.0.1" in text
    assert "WORKER_HEALTH_PORT=8087" in text
    assert "EVOLUTION_HEALTH_PORT=8087" in text
    assert "EVOLUTION_ENABLED=1" in text
