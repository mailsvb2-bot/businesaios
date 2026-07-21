"""Compatibility alias to the canonical runtime outbound transport facade."""

from __future__ import annotations

import importlib
import sys

_OWNER = importlib.import_module("runtime.execution.provider_outbound_sender")
sys.modules[__name__] = _OWNER
