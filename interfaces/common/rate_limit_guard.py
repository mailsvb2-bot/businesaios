from dataclasses import dataclass, field


@dataclass
class RateLimitGuard:
    limits: dict[str, int] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        limit = self.limits.get(key)
        if limit is None:
            return True
        used = self.usage.get(key, 0)
        if used >= limit:
            return False
        self.usage[key] = used + 1
        return True
