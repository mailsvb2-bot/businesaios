from __future__ import annotations

import os

import pytest

from docker.healthcheck import _health_url
from docker.healthcheck import main as docker_healthcheck_main
from scripts.healthcheck import _is_ready_payload


def test_api_container_healthcheck_uses_readyz_by_default(monkeypatch) -> None:
    monkeypatch.delenv("HEALTH_URL", raising=False)
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.setenv("API_PORT", "8000")

    assert _health_url() == "http://127.0.0.1:8000/readyz"


def test_explicit_health_url_is_respected(monkeypatch) -> None:
    monkeypatch.setenv("HEALTH_URL", "http://127.0.0.1:9999/custom")
    monkeypatch.setenv("APP_PROFILE", "api")

    assert _health_url() == "http://127.0.0.1:9999/custom"


def test_readiness_payload_blocks_unwired_runtime() -> None:
    assert _is_ready_payload({"status": "alive", "runtime_wired": False, "ready": False}) is False
    assert _is_ready_payload({"status": "blocked", "runtime_wired": False}) is False
    assert _is_ready_payload({"status": "ready", "runtime_wired": True, "ready": True}) is True


def test_docker_healthcheck_enables_require_ready(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_run_path(path: str, *, run_name: str) -> None:
        captured["path"] = path
        captured["run_name"] = run_name
        captured["health_url"] = os.environ["HEALTH_URL"]
        captured["require_ready"] = os.environ["HEALTHCHECK_REQUIRE_READY"]

    monkeypatch.delenv("HEALTH_URL", raising=False)
    monkeypatch.delenv("HEALTHCHECK_REQUIRE_READY", raising=False)
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.setattr("docker.healthcheck.runpy.run_path", fake_run_path)

    docker_healthcheck_main()

    assert captured == {
        "path": "scripts/healthcheck.py",
        "run_name": "__main__",
        "health_url": "http://127.0.0.1:8000/readyz",
        "require_ready": "1",
    }


def test_scripts_healthcheck_ready_payload_policy_is_fail_closed() -> None:
    assert _is_ready_payload({"ok": False}) is False
    assert _is_ready_payload({"status": "degraded", "ready": True, "runtime_wired": True}) is False
    assert _is_ready_payload({"status": "ok", "ready": True, "runtime_wired": True}) is True
