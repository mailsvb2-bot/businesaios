from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = ROOT / 'runtime'
ALLOWED = {
    ROOT / 'runtime' / 'boot' / 'finance_boot.py',
    ROOT / 'runtime' / 'jobs' / 'run_forecast_job.py',
    ROOT / 'runtime' / 'jobs' / 'run_scenario_evaluation_job.py',
    ROOT / 'runtime' / 'jobs' / 'run_allocation_rebalance_job.py',
}
FORBIDDEN = (
    'StrategicFinanceService(',
    'EconomicsSnapshotToFinancialInputAdapter(',
)


def test_runtime_does_not_construct_finance_domain_objects_outside_finance_boot() -> None:
    offenders: list[str] = []
    for path in sorted(RUNTIME_ROOT.rglob('*.py')):
        if path in ALLOWED:
            continue
        text = path.read_text(encoding='utf-8')
        if any(marker in text for marker in FORBIDDEN):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
