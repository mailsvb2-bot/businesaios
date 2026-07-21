"""Canonical public facade for sealed provider outbound transport."""

from __future__ import annotations

import importlib
import sys

CANON_PROVIDER_OUTBOUND_TRANSPORT_FACADE = True
_OWNER = importlib.import_module("runtime._internal.effects_clients.provider_outbound_sender")
_OWNER.CANON_PROVIDER_OUTBOUND_TRANSPORT_FACADE = True
sys.modules[__name__] = _OWNER
