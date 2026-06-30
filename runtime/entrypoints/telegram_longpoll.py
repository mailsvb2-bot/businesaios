"""BusinesAIOS Telegram entrypoint shim.

This module MUST stay thin.

Heavy wiring lives in:
- runtime/bootstrap/system_builder.py
- runtime/bootstrap/telegram_runner.py

Hard invariants (canonical spec):
- DecisionCore.issue(WorldState) is the only decision source.
- Side-effects only via RuntimeExecutor with valid DecisionEnvelope.
- No SDK/network imports outside runtime/_internal.
"""

from __future__ import annotations


from runtime.boot.env import mark_telegram_token_source
from runtime.boot.system_builder import build_system
from runtime.boot.telegram_runner import run_telegram
from runtime.bootstrap import bootstrap as _bootstrap
from runtime.world_state import WorldStateV1

CANON_RUNTIME_ENTRYPOINT_THIN_SHIM = True
CANON_RUNTIME_ENTRYPOINT_BOOTSTRAP_DELEGATES_TO_SOVEREIGN_BOOTSTRAP = True

# Re-export public wiring helpers expected by main.py and tests.

# Re-export WorldState for demo wrapper.


def runtime_bootstrap() -> None:
    """Explicit bootstrap wrapper.

    Hard invariant: no side-effects on import.
    We load dotenv (for operator ergonomics) only when the sovereign entrypoint
    explicitly boots the process.
    """

    mark_telegram_token_source()
    _bootstrap()
