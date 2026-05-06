from __future__ import annotations

import hashlib
from dataclasses import dataclass

from boot.runtime_boot_report import RuntimeBootReport


@dataclass(frozen=True)
class RuntimeBootFingerprint:
    value: str


def build_boot_fingerprint(report: RuntimeBootReport) -> RuntimeBootFingerprint:
    raw = "|".join(
        f"{record.name}:{record.service_type}:{record.implementation_type}:{','.join(record.dependencies)}"
        for record in report.records
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return RuntimeBootFingerprint(value=digest)
