from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthSession:
    account_id: str = ''
    configured: bool = False
    scopes: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)
