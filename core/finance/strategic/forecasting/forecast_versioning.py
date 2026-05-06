from __future__ import annotations

import hashlib
import json
from decimal import Decimal


class ForecastVersioning:
    def build_version(self, assumptions: dict[str, Decimal]) -> str:
        payload = json.dumps({key: str(value) for key, value in assumptions.items()}, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:12]
