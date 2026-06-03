from __future__ import annotations
CANON_BOOT_LOGGING_SETUP_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True


"""Minimal, production-friendly logging setup.

No side-effects on import. Call explicitly from runtime.bootstrap.bootstrap().
"""

import logging
import os
import re
from collections.abc import Iterable

from runtime.platform.config.env_flags import env_str


_SECRET_KEY_RE = re.compile(r"(TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY|KEY)", re.IGNORECASE)


def _iter_secret_values() -> Iterable[str]:
    """Collect secret values from environment for log redaction.

    We only redact explicit env values to avoid false positives.
    """

    for k, v in os.environ.items():
        if not v:
            continue
        if _SECRET_KEY_RE.search(k) is None:
            continue
        vv = str(v)
        # Skip trivially short values to avoid masking common words.
        if len(vv) < 8:
            continue
        yield vv


class _RedactSecretsFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self._secrets = list(dict.fromkeys(_iter_secret_values()))

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if not self._secrets:
            return True

        try:
            msg = record.getMessage()
        except Exception:
            return True

        redacted = msg
        for s in self._secrets:
            if s and s in redacted:
                redacted = redacted.replace(s, "***")

        # If message was formatted from args, clear args and store final text.
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging() -> None:
    """Configure root logger from env.

Env:
  LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default INFO)

We intentionally keep format compact and stable for log parsing.
"""

    level_name = env_str("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    # force=True to avoid double handlers when running under some runners.
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    # Best-effort secret redaction in logs.
    root = logging.getLogger()
    flt = _RedactSecretsFilter()
    for h in list(root.handlers):
        h.addFilter(flt)
