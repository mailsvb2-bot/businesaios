from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def test_system_builder_uses_runtime_services_result_and_not_dict_style():
    text = _read('runtime/boot/system_builder.py')
    assert 'RuntimeServicesResult' in _read('runtime/boot/system_builder_parts/runtime_services_result.py')
    assert 'services["event_store"]' not in text
    assert 'services["composer"]' not in text


def test_executor_supports_runtime_executor_infra():
    text = _read('runtime/executor.py')
    assert 'RuntimeExecutorInfra' in text
    assert 'runtime_infra' in text
