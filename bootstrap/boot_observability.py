from __future__ import annotations
CANON_BOOT_OBSERVABILITY_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True


"""Boot diagnostics helpers.

Boot should expose operator-readable diagnostics without bypassing structured
logging / observability entirely.
"""

import logging
import time
import uuid
from typing import Any, Iterable, Mapping

from runtime.observability import bind


_BOOT_LOGGER_NAME = "businesaios.boot"


def get_boot_logger() -> logging.Logger:
    return logging.getLogger(_BOOT_LOGGER_NAME)


def emit_boot_diagnostic_lines(*, phase: str, lines: Iterable[str]) -> None:
    logger = get_boot_logger()
    bind(boot_phase=str(phase))
    for line in lines:
        logger.info(str(line))



def _normalize_components(components: Mapping[str, Any] | None) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for key, value in dict(components or {}).items():
        out[str(key)] = bool(value)
    return out


def emit_boot_completed(
    *,
    event_store: Any,
    tenant_id: str,
    run_mode: str,
    env: str,
    components: Mapping[str, Any] | None = None,
) -> None:
    """Emit a canonical boot completion proof event.

    This keeps boot diagnostics observable through the same append-only event
    stream used by the rest of the runtime instead of hiding readiness in logs
    only. No alternate data path is introduced: we append one strict event to
    the existing event store contract.
    """

    normalized_components = _normalize_components(components)
    bind(boot_phase='completed', tenant_id=str(tenant_id), run_mode=str(run_mode), env=str(env))
    logger = get_boot_logger()
    logger.info('boot completed')

    if event_store is None or not hasattr(event_store, 'append_event'):
        raise ValueError('event_store must provide append_event()')

    payload = {
        'run_mode': str(run_mode),
        'env': str(env),
        'components': normalized_components,
        'component_count': len(normalized_components),
        'healthy_component_count': sum(1 for ok in normalized_components.values() if ok),
    }
    event_store.append_event(
        {
            'event_id': str(uuid.uuid4()),
            'tenant_id': str(tenant_id),
            'user_id': 'system',
            'source': 'runtime.boot',
            'event_type': 'runtime_boot_completed',
            'timestamp_ms': int(time.time() * 1000),
            'payload': payload,
            'decision_id': None,
            'correlation_id': None,
        }
    )
