from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Tier‑Ω FINAL: multi‑region signatures (minimal, production-shaped).
# Real deployment should use KMS/HSM per region; here we model it as HMAC per region secret.

@dataclass(frozen=True)
class RegionSignature:
    region: str
    signature_hex: str

@dataclass(frozen=True)
class MultiRegionSignedPayload:
    payload: bytes
    signatures: Tuple[RegionSignature, ...]

def _hmac_sha256(secret: bytes, payload: bytes) -> str:
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()

class RegionSigner:
    def __init__(self, region: str, secret: bytes):
        self.region = region
        self._secret = secret

    def sign(self, payload: bytes) -> RegionSignature:
        return RegionSignature(self.region, _hmac_sha256(self._secret, payload))

class MultiRegionVerifier:
    def __init__(self, region_secrets: Dict[str, bytes], quorum_ratio: float = 2/3):
        self._region_secrets = region_secrets
        self._quorum_ratio = quorum_ratio

    def verify_quorum(self, signed: MultiRegionSignedPayload, required_regions: List[str] | None = None) -> bool:
        required = set(required_regions) if required_regions else set(self._region_secrets.keys())
        total = len(required)
        if total == 0:
            return False

        approvals = 0
        for rs in signed.signatures:
            if rs.region not in required:
                continue
            secret = self._region_secrets.get(rs.region)
            if not secret:
                continue
            expected = _hmac_sha256(secret, signed.payload)
            if hmac.compare_digest(expected, rs.signature_hex):
                approvals += 1

        return approvals >= int(total * self._quorum_ratio + 0.999999)
