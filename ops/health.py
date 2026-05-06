from __future__ import annotations

"""System healthcheck.

This module is SIDE-EFFECT FREE and only probes dependencies via their ping() methods.
"""

from typing import Any, Dict


def system_health(*, ledger, event_store, snapshot_store, outbox=None, delivery_state=None) -> Dict[str, Any]:
    import logging
    _log = logging.getLogger(__name__)

    def _ping(obj) -> bool:
        try:
            if obj is None:
                return False
            if hasattr(obj, "ping"):
                return bool(obj.ping())
            return True
        except (ConnectionError, TimeoutError, OSError) as e:
            _log.warning("health ping failed (recoverable): %s", e)
            return False
        except Exception as e:
            _log.exception("health ping unexpected error: %s", e)
            return False

    return {
        "ledger": _ping(ledger),
        "event_store": _ping(event_store),
        "snapshot": _ping(snapshot_store),
        "outbox": _ping(outbox),
        "delivery_state": _ping(delivery_state),
    }


def health_check(*, ledger, db=None, survival=None):
    """Compatibility health check returning required keys."""
    import logging
    _log = logging.getLogger(__name__)

    try:
        ledger_ok = bool(ledger.verify_chain()) if hasattr(ledger, "verify_chain") else bool(getattr(ledger, "ping", lambda: True)())
    except (ConnectionError, TimeoutError, OSError) as e:
        _log.warning("health_check: ledger failed: %s", e)
        ledger_ok = False
    except Exception as e:
        _log.exception("health_check: ledger unexpected: %s", e)
        ledger_ok = False

    try:
        db_ok = True if db is None else bool(db.ping()) if hasattr(db, "ping") else True
    except (ConnectionError, TimeoutError, OSError) as e:
        _log.warning("health_check: db failed: %s", e)
        db_ok = False
    except Exception as e:
        _log.exception("health_check: db unexpected: %s", e)
        db_ok = False

    try:
        survival_mode = survival.mode() if survival is not None and hasattr(survival, "mode") else None
    except (AttributeError, TypeError) as e:
        _log.warning("health_check: survival.mode failed: %s", e)
        survival_mode = None
    except Exception as e:
        _log.exception("health_check: survival unexpected: %s", e)
        survival_mode = None

    return {"ledger": ledger_ok, "db": db_ok, "survival_mode": survival_mode}


def evolution_health(outbox) -> Dict[str, Any]:
    """Health probe for evolution outbox.

    Read-only: counts pending jobs.
    """
    import logging
    _log = logging.getLogger(__name__)

    try:
        pending = int(outbox.count_pending()) if outbox is not None else 0
        return {"status": "ok", "pending_jobs": pending}
    except (TypeError, ValueError, AttributeError) as e:
        _log.warning("evolution_health: count_pending failed: %s", e)
        return {"status": "error", "error": str(e)}
    except Exception as e:
        _log.exception("evolution_health unexpected: %s", e)
        return {"status": "error", "error": str(e)}
