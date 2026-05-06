from pathlib import Path


def test_root_observability_logger_is_thin_public_surface() -> None:
    content = Path('observability/logger.py').read_text(encoding='utf-8')
    assert 'from observability import' in content
    assert 'get_logger' in content
    assert 'log_kv' in content


def test_runtime_support_logging_is_thin_alias_to_root_surface() -> None:
    content = Path('runtime/platform/support/observability/logging.py').read_text(encoding='utf-8')
    assert 'from observability.logger import' in content
    assert 'def __getattr__' in content
    assert 'get_logger' in content
    assert 'log_kv' in content
