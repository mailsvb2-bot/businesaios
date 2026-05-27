from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_handlers_is_canonical_package() -> None:
    assert (ROOT / 'runtime' / 'handlers' / '__init__.py').exists()
    assert (ROOT / 'runtime' / 'handlers' / 'registry.py').exists()
    assert not (ROOT / 'runtime' / 'handlers.py').exists()


def test_no_critical_handler_uses_runtime_handler_loader() -> None:
    critical_files = [
        ROOT / 'runtime' / 'handlers' / 'ai_ceo_plan.py',
        ROOT / 'runtime' / 'handlers' / 'ads_autopilot_flow.py',
        ROOT / 'runtime' / 'handlers' / 'ads_autopilot_tick.py',
        ROOT / 'runtime' / 'handlers' / 'ads_autopilot' / 'result_format.py',
        ROOT / 'runtime' / 'handlers' / 'ads_autopilot_tick_parts' / 'request_factory.py',
        ROOT / 'runtime' / 'handlers' / 'ads_autopilot_tick_parts' / 'runner.py',
    ]
    for path in critical_files:
        text = path.read_text(encoding='utf-8')
        assert 'runtime.handler_loader' not in text, path.as_posix()
        assert 'import_module_or_file' not in text, path.as_posix()
