from __future__ import annotations

from pathlib import Path

from core.security.release_runtime_surface import is_runtime_release_excluded


def test_root_gitignore_is_single_owner_file() -> None:
    assert Path('.gitignore').exists()
    assert not Path('gitignore').exists()


def test_runtime_release_excludes_root_gitignore_shadow_and_generated_sqlite() -> None:
    assert is_runtime_release_excluded('gitignore', Path('gitignore'))
    assert is_runtime_release_excluded('data/runtime/queue_metrics_rollup.sqlite3', Path('data/runtime/queue_metrics_rollup.sqlite3'))
    assert is_runtime_release_excluded('data/runtime/queue_remediation_audit.sqlite3', Path('data/runtime/queue_remediation_audit.sqlite3'))
    assert is_runtime_release_excluded('data/runtime/queue_remediation_route_history.sqlite3', Path('data/runtime/queue_remediation_route_history.sqlite3'))
