from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS=(
    ROOT / 'interfaces/messaging/_shared/package_surface.py',
    ROOT / 'interfaces/messaging/_shared/provider_surface.py',
    ROOT / 'interfaces/messaging/_shared/provider_runtime.py',
    ROOT / 'interfaces/messaging/channel_common.py',
)
FORBIDDEN=('DecisionCore','send_marketing_offer','one_click_value','launch_campaign','change_price','reward_engine','world_model')

def test_shared_multichannel_owner_modules_stay_transport_only():
    offenders=[]
    for path in TARGETS:
        text=path.read_text(encoding='utf-8')
        for item in FORBIDDEN:
            if item in text:
                offenders.append(f'{path.as_posix()}: {item}')
    assert not offenders, offenders
