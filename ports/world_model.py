from __future__ import annotations

CANON_WORLD_MODEL_CONTRACT_FINAL_OWNER = True
CANON_PORTS_WORLD_MODEL_OWNER = True
CANON_BOOT_WIRING_ONLY = True


from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DecisionWorldModelPort(Protocol):
    """
    Единственный допустимый контракт world model для DecisionCore.

    Важно:
    - DecisionCore не должен знать про конкретный LTVModel
    - DecisionCore не должен знать про конкретный PricingWorldModel
    - только enrich_state(state) -> state
    """

    def enrich_state(self, state: Any) -> Any:
        ...

WORLD_MODEL_CANON_VERSION = "WM-CONTRACT-V2"
