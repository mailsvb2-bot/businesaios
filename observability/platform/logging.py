from __future__ import annotations

import logging
from typing import Any

from shared.types import ensure_jsonable


_FORMAT = '%(asctime)s %(levelname)s %(name)s %(message)s'
CANON_PLATFORM_LOGGING_PUBLIC_API = True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_kv(logger: logging.Logger, message: str, **fields: Any) -> None:
    ordered = ' '.join(f'{key}={value!r}' for key, value in sorted(ensure_jsonable(fields).items()))
    logger.info('%s %s', message, ordered)


__all__ = ['CANON_PLATFORM_LOGGING_PUBLIC_API', 'get_logger', 'log_kv']
