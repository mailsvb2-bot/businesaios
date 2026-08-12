from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


LEGACY_TOKENS = [
    "organization_platform",
    "BUSINESAIOS",
    "BusinesAIOS",
    "metro_",
    "metro-",
]


def _read_text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def test_deployment_contract_exists_and_has_anchors() -> None:
    p = ROOT / "docs" / "DEPLOYMENT_CONTRACT.md"
    assert p.exists(), "Missing docs/DEPLOYMENT_CONTRACT.md (canonical deployment contract)."
    txt = _read_text(p)
    assert "Deployment Contract (Canonical) — BusinesAIOS" in txt
    assert "Canonical app_id:" in txt
    assert "APP_PROFILE=api" in txt
    assert "APP_PROFILE=worker" in txt
    assert "APP_PROFILE=telegram" in txt
    assert "businesaios-api.service" in txt
    assert "businesaios-worker.service" in txt
    assert "GET /health" in txt
    assert "GET /readyz" in txt
    assert "WORKER_HEALTH_PORT" in txt
    assert "EVOLUTION_HEALTH_PORT" in txt  # internal compatibility name only


def test_no_legacy_identifiers_in_deploy_and_k8s() -> None:
    targets = [
        ROOT / "deploy",
        ROOT / "infrastructure" / "k8s",
        ROOT / ".env.example",
    ]

    offending: list[str] = []

    def check_file(fp: pathlib.Path) -> None:
        txt = _read_text(fp)
        for tok in LEGACY_TOKENS:
            if tok in txt:
                offending.append(f"{fp.relative_to(ROOT)} contains legacy token: {tok!r}")

    for t in targets:
        if t.is_file():
            check_file(t)
            continue
        for fp in t.rglob("*"):
            if fp.is_file():
                check_file(fp)

    assert not offending, "Deployment drift / legacy identifiers detected:\n" + "\n".join(offending)


def test_compose_has_canonical_service_and_volume_names() -> None:
    compose = ROOT / "deploy" / "docker-compose.yml"
    assert compose.exists(), "Missing deploy/docker-compose.yml"
    txt = _read_text(compose)
    assert "businesaios_api:" in txt
    assert "businesaios_worker:" in txt
    assert "businesaios_connector_telegram:" in txt
    assert "container_name: businesaios_api" in txt
    assert "container_name: businesaios_worker" in txt
    assert "container_name: businesaios_connector_telegram" in txt
    assert "APP_PROFILE: api" in txt
    assert "APP_PROFILE: worker" in txt
    assert "APP_PROFILE: telegram" in txt
    assert 'profiles: ["telegram"]' in txt
    assert "businesaios_data:" in txt
    assert "businesaios_data:/app/runtime/data" in txt
    assert "dockerfile: Dockerfile" in txt
    assert "deploy/Dockerfile" not in txt
    assert "businesaios_telegram:" not in txt
    assert "businesaios_evolution:" not in txt


def test_systemd_install_uses_canonical_app_dir_and_units() -> None:
    install = ROOT / "deploy" / "systemd" / "install.sh"
    assert install.exists(), "Missing deploy/systemd/install.sh"
    txt = _read_text(install)
    assert 'APP_DIR="${APP_DIR:-/opt/businesaios}"' in txt
    assert 'STATE_FILE="${STATE_FILE:-${STATE_DIR}/release_state.json}"' in txt
    assert 'DeploymentStateStore' in txt
    assert "businesaios-api.service" in txt
    assert "businesaios-worker.service" in txt
    assert "businesaios-connector-telegram.service" in txt
    # Historical names remain only so the installer can disable/remove them during migration.
    assert "businesaios-telegram.service" in txt
    assert "businesaios-evolution.service" in txt
