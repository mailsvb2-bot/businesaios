from __future__ import annotations

from typing import Protocol

from economics.contracts import TruthFragment

CANON_RUNTIME_ECONOMIC_CORE_CONTRACTS = True


class TruthFragmentProvider(Protocol):
    def get_truth_fragment(self, entity_id: str, *, lead_id: str | None = None) -> TruthFragment | None: ...
