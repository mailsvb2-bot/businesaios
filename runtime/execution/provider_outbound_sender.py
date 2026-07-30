"""Canonical compatibility alias for the sealed provider transport owner."""

from __future__ import annotations

import sys

from runtime.firewall.import_guard import allow_internal_import

with allow_internal_import():
    from runtime._internal.effects_clients import provider_outbound_sender as _OWNER

_OWNER.CANON_PROVIDER_OUTBOUND_TRANSPORT_FACADE = True
sys.modules[__name__] = _OWNER
