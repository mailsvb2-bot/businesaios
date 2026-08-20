from __future__ import annotations

from pathlib import Path

from core.safety.operational.runtime_bootstrap import resolve_operational_safety_runtime


def test_runtime_bootstrap_uses_default_runtime_root(tmp_path: Path) -> None:
    runtime = resolve_operational_safety_runtime(default_root=tmp_path)
    runtime.service.precheck  # smoke anchor
    assert (tmp_path / 'operational_budget').exists() or runtime is not None


def test_runtime_bootstrap_uses_explicit_env_paths(tmp_path: Path, monkeypatch) -> None:
    ledger_path = tmp_path / 'custom-ledger.json'
    policy_path = tmp_path / 'policy.json'
    policy_path.write_text('{"default_policy": {"max_actions_per_hour": 3}}', encoding='utf-8')
    monkeypatch.setenv('BUSINESAIOS_OPERATIONAL_BUDGET_LEDGER', str(ledger_path))
    monkeypatch.setenv('BUSINESAIOS_OPERATIONAL_BUDGET_POLICY_JSON', str(policy_path))
    runtime = resolve_operational_safety_runtime(default_root=tmp_path)
    assert runtime.policy_provider.for_tenant('any').max_actions_per_hour == 3
    monkeypatch.delenv('BUSINESAIOS_OPERATIONAL_BUDGET_LEDGER', raising=False)
    monkeypatch.delenv('BUSINESAIOS_OPERATIONAL_BUDGET_POLICY_JSON', raising=False)


def test_runtime_bootstrap_uses_systemd_shared_runtime_root(tmp_path: Path, monkeypatch) -> None:
    for name in (
        'BUSINESAIOS_DATA_DIR',
        'APP_RUNTIME_DATA_DIR',
        'BAIOS_DATA_DIR',
        'DATA_DIR',
        'BUSINESAIOS_OPERATIONAL_BUDGET_LEDGER',
    ):
        monkeypatch.delenv(name, raising=False)
    runtime_root = tmp_path / 'runtime'
    legacy_root = tmp_path / 'legacy-relative-root'
    monkeypatch.setenv('APP_RUNTIME_DATA_DIR', str(runtime_root))

    resolve_operational_safety_runtime(default_root=legacy_root)

    assert (runtime_root / 'operational_budget').is_dir()
    assert not (legacy_root / 'operational_budget').exists()
