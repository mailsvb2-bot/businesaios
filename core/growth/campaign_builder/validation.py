from __future__ import annotations

from dataclasses import dataclass

from .contracts import AutopilotCampaignBuildRequest


@dataclass(frozen=True)
class CampaignBuildValidationError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}: {self.message}"


def validate_build_request(req: AutopilotCampaignBuildRequest) -> None:
    if not str(req.tenant_id or "").strip():
        raise CampaignBuildValidationError("tenant_id", "must be non-empty")
    if not str(req.platform or "").strip():
        raise CampaignBuildValidationError("platform", "must be non-empty")
    if not str(req.account_id or "").strip():
        raise CampaignBuildValidationError("account_id", "must be non-empty")

    if not str(req.offer_title or "").strip():
        raise CampaignBuildValidationError("offer_title", "must be non-empty")
    if not str(req.what or "").strip():
        raise CampaignBuildValidationError("what", "must be non-empty")
    if not str(req.region or "").strip():
        raise CampaignBuildValidationError("region", "must be non-empty")

    if int(req.total_budget_minor_7d) <= 0:
        raise CampaignBuildValidationError("total_budget_minor_7d", "must be > 0")
    if not str(req.budget_currency or "").strip():
        raise CampaignBuildValidationError("budget_currency", "must be non-empty")

    if int(req.target_cac_minor) < 0:
        raise CampaignBuildValidationError("target_cac_minor", "must be >= 0")
