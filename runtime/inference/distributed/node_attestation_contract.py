from __future__ import annotations

from dataclasses import dataclass


CANON_RUNTIME_DISTRIBUTED_NODE_ATTESTATION_CONTRACT = True


@dataclass(frozen=True)
class DistributedInferenceNodeAttestation:
    node_id: str
    attested: bool
    evidence: str


class DistributedInferenceNodeAttestationPolicy:
    def allows(self, attestation: DistributedInferenceNodeAttestation) -> bool:
        return bool(attestation.attested and str(attestation.evidence).strip())
