from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    ROOT / 'runtime/messaging_policy_alert_subscriptions/notifier.py',
    ROOT / 'runtime/messaging_policy_alert_dedup/notifier.py',
    ROOT / 'runtime/messaging_policy_alert_dedup_persistent/tenant_notifier.py',
]

def test_alert_notifiers_remain_observability_only() -> None:
    forbidden=('DecisionCore','send_marketing_offer','one_click_value','launch_campaign','change_price','start_sales_flow')
    offenders=[]
    for path in TARGETS:
        if not path.exists():
            continue
        text=path.read_text(encoding='utf-8')
        for item in forbidden:
            if item in text:
                offenders.append(f'{path.as_posix()}: {item}')
    assert not offenders, offenders
