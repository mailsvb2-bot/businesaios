from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS=(
    ROOT / 'runtime/messaging_policy_alerts',
    ROOT / 'runtime/messaging_policy_alert_subscriptions',
    ROOT / 'runtime/messaging_policy_dashboard',
    ROOT / 'runtime/messaging_policy_trace',
)

def test_runtime_messaging_observability_packages_do_not_import_runtime_boot_web():
    offenders=[]
    for base in TARGETS:
        if not base.exists():
            continue
        for path in base.rglob('*.py'):
            text=path.read_text(encoding='utf-8')
            if 'runtime.boot.web' in text:
                offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, offenders
