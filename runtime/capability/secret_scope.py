
class SecretScope:
    """Restricts secret access to allowed keys only."""

    def __init__(self, provider, allowed_keys):
        self.provider = provider
        self.allowed = set(allowed_keys)

    def get(self, key: str) -> str:
        if key not in self.allowed:
            raise RuntimeError("Secret access denied")
        return self.provider.get(key)
