from __future__ import annotations

from typing import Protocol, runtime_checkable

from runtime.ports.effects_admin import EffectsAdminPort
from runtime.ports.effects_comms import EffectsCommsPort
from runtime.ports.effects_revenue import EffectsRevenuePort


@runtime_checkable
class EffectsPort(
    EffectsCommsPort,
    EffectsRevenuePort,
    EffectsAdminPort,
    Protocol,
):
    """EffectsPort is the ONLY abstraction through which irreversible actions occur.

    IMPORTANT:
    - Implementations MUST live in runtime/_internal.
    - This interface MUST be used by handlers.
    - Handlers MUST NOT import any SDKs / clients directly.
    """
    pass
