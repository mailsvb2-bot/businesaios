from __future__ import annotations

from dataclasses import dataclass

# Tier‑Ω FINAL: signed quorum gate (BFT‑shaped).
# The real system would verify cryptographic signatures and membership; here it's a clean contract.

@dataclass(frozen=True)
class SignedVote:
    region: str
    approve: bool
    signature_ok: bool  # result of crypto verification in infra layer

def bft_signed_quorum(votes: list[SignedVote]) -> bool:
    """Requires >= 2/3 approvals among signature‑valid votes."""
    valid = [v for v in votes if v.signature_ok]
    if not valid:
        return False
    approvals = sum(1 for v in valid if v.approve)
    n = len(valid)
    return approvals >= (2 * n // 3 + 1)
