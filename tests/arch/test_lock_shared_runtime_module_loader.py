from pathlib import Path


FILES = [
    'runtime/handlers/ai_ceo_plan.py',
    'runtime/handlers/ads_autopilot_flow.py',
    'runtime/handlers/ads_autopilot_tick.py',
    'runtime/handlers/ads_autopilot/result_format.py',
    'runtime/handlers/ads_autopilot_tick_parts/request_factory.py',
    'runtime/handlers/ads_autopilot_tick_parts/runner.py',
]


def test_critical_runtime_handlers_use_direct_package_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel in FILES:
        text = (root / rel).read_text(encoding='utf-8')
        assert 'runtime.handler_loader' not in text, rel
        assert 'import_module_or_file' not in text, rel
        assert 'spec_from_file_location' not in text, rel
