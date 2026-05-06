from pathlib import Path


def test_system_builder_uses_split_helpers_v26():
    text = Path("bootstrap/system_builder.py").read_text(encoding="utf-8")
    assert "run_product_preflight" in text
    assert "wire_ads_stack" in text


def test_update_processor_uses_split_helpers_v26():
    text = Path("interfaces/telegram/pipeline/update_processor.py").read_text(encoding="utf-8")
    assert "build_worldstate_with_overlays" in text
    assert "emit_behavior_telemetry" in text
    assert "run_decision_and_execution" in text
    assert "current_tenant_id_REMOVED" not in text


def test_ads_apply_handler_uses_helper_surface_v26():
    text = Path("runtime/handlers/ads_apply_execute.py").read_text(encoding="utf-8")
    assert "build_apply_request" in text
    assert "summary_text" in text
