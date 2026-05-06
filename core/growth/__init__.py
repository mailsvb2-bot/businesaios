"""Growth modules (attribution, budget guardrails, bandit choices).

Kept separate from core/marketing to avoid mixing UX copy with control loops.
"""

from __future__ import annotations

import sys
from importlib import import_module

CANON_COMPAT_SHIM = True

_COMPAT_ALIAS_MAP = {
    "spend_ledger_eventstore": "core.growth.spend_ledger_event_store",
}

for _alias_name, _target_module_name in _COMPAT_ALIAS_MAP.items():
    _target = import_module(_target_module_name)
    sys.modules[f"{__name__}.{_alias_name}"] = _target
    globals()[_alias_name] = _target
