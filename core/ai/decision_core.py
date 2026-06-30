from __future__ import annotations

import logging

from application.decision_policy.pricing import allowed_price_band, band_rank, merge_price_constraints
from application.decision_runtime.run import run_decision
from core.decision_core_contract import CANONICAL_DECISION_CORE_IMPORT_PATH
from kernel.decision_signer import DecisionSigner
from ports.world_model import DecisionWorldModelPort

logger = logging.getLogger(__name__)
ENVELOPE_VERSION = 1
SOVEREIGN_DECISION_CORE = True


def _sign_payload(payload: dict, *, secret: bytes) -> str:
    return DecisionSigner.sign(payload=payload, secret=secret)


class DecisionCore:
    """The ONLY decision issuance point.
    Contract:
      decide(WorldState) -> DecisionEnvelope
    Invariants:
      - no side-effects
      - always emits proof event decision_issued
    """

    CANONICAL_IMPORT_PATH = CANONICAL_DECISION_CORE_IMPORT_PATH
    IS_SOVEREIGN_DECISION_CORE = True

    def __init__(
        self,
        selector,
        keyring,
        schema_registry,
        snapshot_store,
        event_log,
        decision_archive=None,
        ttl_ms: int = 5 * 60 * 1000,
        world_model: DecisionWorldModelPort | None = None,
        issuer_id: str = "businesaios-core",
    ):
        self._selector = selector
        self._keyring = keyring
        self._schemas = schema_registry
        self._snapshots = snapshot_store
        self._events = event_log
        self._archive = decision_archive
        self._ttl_ms = int(ttl_ms)
        self._issuer_id = str(issuer_id or "businesaios-core").strip() or "businesaios-core"

        if world_model is not None and not isinstance(world_model, DecisionWorldModelPort):
            raise TypeError(
                "DecisionCore.world_model must implement DecisionWorldModelPort "
                "(canonical enrich_state contract)"
            )
        self._world_model: DecisionWorldModelPort | None = world_model

    @staticmethod
    def _band_rank(band: str | None) -> int:
        return band_rank(band)

    def _allowed_price_band(self, state) -> str:
        """Compatibility shim for older callers/tests.

        The canonical implementation lives in core.ai.decision_pricing.allowed_price_band.
        DecisionCore delegates there and keeps no second pricing brain.
        """
        return allowed_price_band(state=state, logger=logger)

    def _merge_price_constraints(self, *, base: dict | None, override: dict | None) -> dict:
        """Compatibility shim for conservative band merging.

        Canonical implementation lives in core.ai.decision_pricing.merge_price_constraints.
        """
        return merge_price_constraints(base=base, override=override, logger=logger)

    def decide(self, state):
        return run_decision(core=self, state=state, envelope_version=ENVELOPE_VERSION, logger=logger)

    def optimize(self, state):
        """Canonical alias used by runtime and tests. Still routes to the single decision issuer."""
        return self.decide(state)

    def issue(self, state):
        """Compatibility alias for orchestrators. No alternate brain is introduced."""
        return self.optimize(state)
