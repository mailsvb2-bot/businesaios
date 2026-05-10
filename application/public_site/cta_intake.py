from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

CANON_PUBLIC_SITE_CTA_INTAKE = True


@dataclass(frozen=True)
class CTASubmitResult:
    intake_id: str
    created_at: str
    app_url: str
    outcome: str = "intake_recorded"


@dataclass(frozen=True)
class CTAIntakeStatus:
    intake_id: str
    found: bool
    outcome: str
    created_at: str


class CTALandingIntakeService:
    def __init__(
        self,
        *,
        storage_path: str = "runtime_state/pilot_applications.jsonl",
        app_base_url: str = "https://app.businessaios.ru",
    ) -> None:
        self._storage_path = Path(storage_path)
        self._app_base_url = app_base_url.rstrip("/")

    def submit(self, *, payload: dict[str, object]) -> CTASubmitResult:
        intake_id = f"cta-{uuid4().hex[:16]}"
        created_at = datetime.now(timezone.utc).isoformat()
        row = {
            "intake_id": intake_id,
            "created_at": created_at,
            "source": "public_landing_cta",
            "payload": dict(payload),
            "outcome": "intake_recorded",
        }
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return CTASubmitResult(
            intake_id=intake_id,
            created_at=created_at,
            app_url=f"{self._app_base_url}/?intake_id={intake_id}",
        )

    def get_status(self, *, intake_id: str) -> CTAIntakeStatus:
        token = str(intake_id or "").strip()
        if not token or not self._storage_path.exists():
            return CTAIntakeStatus(
                intake_id=token,
                found=False,
                outcome="not_found",
                created_at="",
            )

        for line in self._storage_path.read_text(encoding="utf-8").splitlines()[::-1]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if str(row.get("intake_id") or "") == token:
                return CTAIntakeStatus(
                    intake_id=token,
                    found=True,
                    outcome=str(row.get("outcome") or "intake_recorded"),
                    created_at=str(row.get("created_at") or ""),
                )

        return CTAIntakeStatus(
            intake_id=token,
            found=False,
            outcome="not_found",
            created_at="",
        )


__all__ = [
    "CANON_PUBLIC_SITE_CTA_INTAKE",
    "CTALandingIntakeService",
    "CTASubmitResult",
    "CTAIntakeStatus",
]
