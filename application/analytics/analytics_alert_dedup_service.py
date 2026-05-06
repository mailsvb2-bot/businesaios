from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Mapping


def _alert_fingerprint(alert: Mapping[str, object]) -> str:
    raw = '|'.join([str(alert.get('tenant_id') or ''), str(alert.get('source_kind') or ''), str(alert.get('severity') or ''), str(alert.get('metric_id') or ''), str(alert.get('summary') or '')])
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class AnalyticsAlertDedupService:
    def deduplicate(self, *, alerts: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
        seen: set[str] = set()
        out: list[dict[str, object]] = []
        for alert in alerts:
            payload = dict(alert)
            fp = _alert_fingerprint(payload)
            if fp in seen:
                continue
            seen.add(fp)
            payload['fingerprint'] = fp
            out.append(payload)
        return out
