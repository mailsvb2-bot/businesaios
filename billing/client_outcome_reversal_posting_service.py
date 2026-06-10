from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from billing.client_outcome_reversal_contract import ClientOutcomeReversalRecord
from billing.client_outcome_reversal_ledger_bridge import ClientOutcomeReversalLedgerBridge
from billing.ledger_event import LedgerPosting
from billing.ledger_store import LedgerStoreContract

CANON_CLIENT_OUTCOME_REVERSAL_POSTING_SERVICE = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeReversalPostingResult:
    posting: LedgerPosting
    appended: bool


@dataclass(frozen=True, slots=True)
class ClientOutcomeReversalPostingService:
    ledger_store: LedgerStoreContract
    ledger_bridge: ClientOutcomeReversalLedgerBridge

    def append_reversal(self, *, reversal: ClientOutcomeReversalRecord, booked_at: datetime) -> ClientOutcomeReversalPostingResult:
        posting = self.ledger_bridge.build_posting(reversal=reversal, booked_at=booked_at)
        stored = self.ledger_store.append(posting)
        return ClientOutcomeReversalPostingResult(
            posting=stored,
            appended=stored == posting,
        )
