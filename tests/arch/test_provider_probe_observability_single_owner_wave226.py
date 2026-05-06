from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_live_probe_observability_payload_owned_by_single_helper():
    owner = ROOT / 'runtime/business_autonomy/provider_probe_observability_payload.py'
    text = owner.read_text(encoding='utf-8')
    assert 'build_live_probe_labels' in text
    assert 'build_live_probe_gauge_payload' in text

    target = ROOT / 'runtime/business_autonomy/provider_runtime_observability.py'
    src = target.read_text(encoding='utf-8')
    assert 'build_live_probe_labels' in src
    assert 'build_live_probe_gauge_payload' in src
    assert "'messaging_channel'" not in src
    assert "'messaging_reason'" not in src
