from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROVIDER_DIRS=(
    ROOT / 'interfaces/messaging/whatsapp',
    ROOT / 'interfaces/messaging/sms',
    ROOT / 'interfaces/messaging/email',
    ROOT / 'interfaces/messaging/instagram',
    ROOT / 'interfaces/messaging/messenger',
    ROOT / 'interfaces/regional/line',
    ROOT / 'interfaces/regional/wechat',
    ROOT / 'interfaces/regional/kakaotalk',
    ROOT / 'interfaces/regional/viber',
)
FORBIDDEN_FILES={'adapter.py','runner.py','runner_components.py','runner_helpers.py','outbound_sender.py','delivery_mapper.py','inbound_normalizer.py','config.py'}

def test_provider_packages_do_not_regrow_local_implementation_files():
    offenders=[]
    for base in PROVIDER_DIRS:
        if not base.exists():
            continue
        names={p.name for p in base.iterdir() if p.is_file()}
        bad=sorted(names & FORBIDDEN_FILES)
        if bad:
            offenders.append(f'{base.as_posix()}: {bad}')
    assert not offenders, offenders
