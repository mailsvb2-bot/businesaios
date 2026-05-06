from runtime.platform.config.env_flags import env_str


class EnvSecretProvider:
    def get(self, key: str) -> str:
        value = env_str(key, "")
        if not value:
            raise RuntimeError(f"Secret not found: {key}")
        return value
