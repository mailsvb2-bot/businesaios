import os

from config.startup_barriers import apply_startup_barriers


def test_apply_startup_barriers_sets_hermetic_env_defaults(monkeypatch) -> None:
    for key in ('PYTHONDONTWRITEBYTECODE', 'PYTHONPYCACHEPREFIX', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD', 'DD_TRACE_ENABLED', 'DD_TRACE_STARTUP_LOGS'):
        monkeypatch.delenv(key, raising=False)
    apply_startup_barriers()
    assert os.environ['PYTHONDONTWRITEBYTECODE'] == '1'
    assert os.environ['PYTHONPYCACHEPREFIX'] == '/tmp/pycache'
    assert os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
    assert os.environ['DD_TRACE_ENABLED'] == '0'
    assert os.environ['DD_TRACE_STARTUP_LOGS'] == '0'
