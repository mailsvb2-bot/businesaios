from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RateLimitGuard:
    limits: Dict[str, int] = field(default_factory=dict)
    usage: Dict[str, int] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        limit = self.limits.get(key)
        if limit is None:
            return True
        used = self.usage.get(key, 0)
        if used >= limit:
            return False
        self.usage[key] = used + 1
        return True
