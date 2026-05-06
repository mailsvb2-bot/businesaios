from __future__ import annotations

import logging

logger = logging.getLogger("businesaios.arch")

def log_arch_violation(code: str, *, details: str | None = None) -> None:
    msg = f"ARCH_VIOLATION:{code}"
    if details:
        msg += f" details={details}"
    logger.critical(msg)
