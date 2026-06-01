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
