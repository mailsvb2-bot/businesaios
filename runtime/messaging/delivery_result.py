from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    channel: str
    mode: str
    external_id: str
    detail: dict | None = None

    @property
    def success(self) -> bool:
        return bool(self.ok)

    @property
    def message_id(self) -> str:
        return str(self.external_id or "")

    @property
    def error(self) -> str | None:
        if self.ok:
            return None
        details = dict(self.detail or {})
        return str(details.get("reason") or details.get("error") or "")
