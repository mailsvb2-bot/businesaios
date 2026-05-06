from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    ROOT / 'runtime/messaging_policy_alert_dedup_persistent/boot.py',
    ROOT / 'runtime/messaging_policy_alert_dedup_persistent/subscription_service_factory.py',
]

def test_legacy_single_tenant_binding_surfaces_are_no_longer_preferred_owner_paths() -> None:
    offenders=[]
    for path in TARGETS:
        if not path.exists():
            continue
        text=path.read_text(encoding='utf-8')
        if 'tenant_id:' in text and 'normalize_tenant_scope' in text:
            offenders.append(path.as_posix())
    assert not offenders, offenders
