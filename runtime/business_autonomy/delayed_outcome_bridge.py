"""Compatibility alias for the platform-owned delayed outcome bridge."""

from __future__ import annotations

import sys

from runtime.platform import business_autonomy_delayed_outcome_bridge as _OWNER

sys.modules[__name__] = _OWNER
