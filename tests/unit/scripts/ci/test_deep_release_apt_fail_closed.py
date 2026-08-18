from __future__ import annotations

from pathlib import Path


def test_deep_release_apt_network_waits_are_bounded_and_fail_closed() -> None:
    root = Path(__file__).resolve().parents[4]
    workflow = (root / ".github/workflows/deep-release-validation.yml").read_text(encoding="utf-8")
    start = workflow.index("- name: Install release dependencies and PostgreSQL client")
    end = workflow.index("- name: Install locked frontend dependencies and browsers", start)
    step = workflow[start:end]

    assert "set -Eeuo pipefail" in step
    assert "Acquire::Retries=3" in step
    assert "Acquire::http::Timeout=20" in step
    assert "Acquire::https::Timeout=20" in step
    assert step.count("timeout --signal=TERM --kill-after=30s 5m apt-get") == 2
    assert "apt-get \"${APT_BOUNDS[@]}\" update" in step
    assert "apt-get \"${APT_BOUNDS[@]}\" install -y --no-install-recommends postgresql-client" in step
    for command in ("pg_isready", "psql", "pg_dump", "pg_restore"):
        assert f"command -v {command} >/dev/null" in step
    assert "|| true" not in step
