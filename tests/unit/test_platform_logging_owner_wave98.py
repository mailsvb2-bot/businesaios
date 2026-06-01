from __future__ import annotations

import observability.logger as root_logging
import runtime.platform.support.observability.logging as runtime_logging
from observability.platform.logging import (
    CANON_PLATFORM_LOGGING_PUBLIC_API,
)
from observability.platform.logging import (
    get_logger as platform_get_logger,
)
from observability.platform.logging import (
    log_kv as platform_log_kv,
)


def test_root_and_runtime_logging_surfaces_reexport_platform_owner() -> None:
    assert CANON_PLATFORM_LOGGING_PUBLIC_API is True
    assert root_logging.get_logger is platform_get_logger
    assert runtime_logging.get_logger is platform_get_logger
    assert root_logging.log_kv is platform_log_kv
    assert runtime_logging.log_kv is platform_log_kv


def test_platform_get_logger_preserves_handler_setup() -> None:
    logger = platform_get_logger('wave98.test.logger')
    assert logger.name == 'wave98.test.logger'
    assert logger.handlers
    assert logger.propagate is False
