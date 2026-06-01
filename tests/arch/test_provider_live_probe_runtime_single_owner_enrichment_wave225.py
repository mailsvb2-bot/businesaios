from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_provider_live_probe_runtime_uses_single_owner_enricher():
    path = ROOT / "runtime/business_autonomy/provider_live_probe_runtime.py"
    text = path.read_text(encoding="utf-8")

    assert "enrich_probe_result_with_messaging_health" in text
    assert "finalize_probe_result" in text

    forbidden = (
        "apply_provider_probe_result_to_registry(",
        "signal_to_metadata(",
    )
    offenders = [item for item in forbidden if item in text]
    assert not offenders, offenders
