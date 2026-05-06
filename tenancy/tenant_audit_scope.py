from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_AUDIT_SCOPE = True


@dataclass(frozen=True)
class TenantAuditScope:
    tenant_id: str
    retention_days: int = 365
    export_enabled: bool = False
    include_payloads: bool = False
    pii_redaction_enabled: bool = True
    redacted_fields: tuple[str, ...] = (
        "token",
        "password",
        "secret",
        "authorization",
        "cookie",
    )
    required_labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if int(self.retention_days) < 1:
            raise ValueError("retention_days must be >= 1")

    def scrub(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self.validate()
        cleaned: dict[str, Any] = {}
        sensitive = {str(item).lower() for item in self.redacted_fields}

        for key, value in dict(payload).items():
            text_key = str(key)
            if text_key.lower() in sensitive:
                cleaned[text_key] = "[REDACTED]"
            elif not self.include_payloads and text_key == "payload":
                cleaned[text_key] = "[OMITTED]"
            else:
                cleaned[text_key] = value

        for label_key, label_value in self.required_labels.items():
            cleaned.setdefault(str(label_key), str(label_value))
        cleaned.setdefault("tenant_id", self.tenant_id)
        return cleaned


__all__ = ["CANON_TENANT_AUDIT_SCOPE", "TenantAuditScope"]
