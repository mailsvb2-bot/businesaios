from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StepKey:
    domain: str
    step: str
    offer_id: str | None = None

    def render(self) -> str:
        if self.offer_id:
            return f"{self.domain}:{self.step}:offer:{self.offer_id}"
        return f"{self.domain}:{self.step}"


def ux_step_key(*, domain: str, step: str, offer_id: str | None = None) -> str:
    return StepKey(domain=str(domain), step=str(step), offer_id=(str(offer_id) if offer_id else None)).render()
