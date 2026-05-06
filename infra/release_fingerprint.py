from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseFingerprint:
    value: str


def build_release_fingerprint(*, version: str, environment: str) -> ReleaseFingerprint:
    raw = f"{version}|{environment}"
    return ReleaseFingerprint(
        value=hashlib.sha256(raw.encode("utf-8")).hexdigest()
    )
