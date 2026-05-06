from __future__ import annotations

"""Ring-level healthcheck.

This is *not* a bypass. It reads liveness from ports and storages.
"""

def ring_health(event_log, ledger, outbox):
    return {
        "event_log": event_log.ping() if hasattr(event_log, "ping") else True,
        "ledger": ledger.ping() if hasattr(ledger, "ping") else True,
        "outbox": outbox.ping() if hasattr(outbox, "ping") else True,
    }
