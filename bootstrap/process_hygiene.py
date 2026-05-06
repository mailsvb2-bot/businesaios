from __future__ import annotations
import os
import sys
import warnings
from runtime.platform.config.env_flags import env_str

def apply_process_hygiene() -> None:
    sys.dont_write_bytecode = True
    os.environ.setdefault('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
    os.environ.setdefault('DD_TRACE_ENABLED', 'false')
    os.environ.setdefault('DD_TRACE_STARTUP_LOGS', '0')
    warnings.filterwarnings('ignore', message=r".*swap memory stats couldn't be determined.*", category=RuntimeWarning, module=r'ddtrace\\.vendor\\.psutil\\..*')
    warnings.filterwarnings('ignore', message=r'.*\/proc\/vmstat.*', category=RuntimeWarning)
    warnings.filterwarnings('ignore', category=RuntimeWarning, module=r'psutil\..*')

def maybe_disable_singleton_lock_in_dev_test() -> None:
    app_env = env_str('APP_ENV', env_str('ENV', 'dev')).lower()
    if app_env != 'prod' or env_str('PYTEST_CURRENT_TEST', ''):
        os.environ['DISABLE_SINGLETON_LOCK'] = '1'
