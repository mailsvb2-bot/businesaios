from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit

from config.config_versioning import ConfigVersion, utc_now
from config.versioned_config_store import (
    InMemoryVersionedConfigStore,
    PersistentVersionedConfigStore,
    canonical_labels,
    require_text,
    require_timezone_aware,
)
from core.tenancy.normalization import require_tenant_id


@dataclass(frozen=True)
class LLMProviderPolicy:
    default_openai_compat_model: str = "gpt-4.1-mini"
    default_timeout_s: int = 20
    mock_fixed_text: str = "OK"


DEFAULT_LLM_PROVIDER_POLICY = LLMProviderPolicy()


class SalesAIDataMode(StrEnum):
    REDACTED = "redacted"
    STANDARD = "standard"
    NO_CLOUD = "no_cloud"


def _business_id(value: object) -> str:
    return require_text("business_id", value)


def _provider(value: object) -> str:
    return require_text("provider", value).casefold()


def _provider_base_url(value: object) -> str:
    raw = require_text("base_url", value).rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ValueError("sales AI provider base_url must use https")
    if parsed.username or parsed.password:
        raise ValueError("sales AI provider base_url must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("sales AI provider base_url must not contain query or fragment")
    host = parsed.hostname.casefold()
    port = parsed.port
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path.rstrip("/")
    return urlunsplit(("https", netloc, path, "", ""))


@dataclass(frozen=True)
class SalesAIConsentSnapshot:
    tenant_id: str
    business_id: str
    enabled: bool
    provider: str
    base_url: str
    data_mode: SalesAIDataMode = SalesAIDataMode.REDACTED
    customer_notice_confirmed: bool = False
    consent_epoch: int = 0
    updated_at: datetime = field(default_factory=utc_now)
    labels: Mapping[str, str] = field(default_factory=dict)
    version: ConfigVersion | None = None

    @property
    def provider_target(self) -> str:
        return f"{self.provider}|{self.base_url}"

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        _business_id(self.business_id)
        provider = _provider(self.provider)
        base_url = _provider_base_url(self.base_url)
        if provider != self.provider or base_url != self.base_url:
            raise ValueError("sales AI consent snapshot must be normalized")
        if isinstance(self.consent_epoch, bool) or int(self.consent_epoch) < 0:
            raise ValueError("consent_epoch must be a non-negative integer")
        if self.enabled and int(self.consent_epoch) < 1:
            raise ValueError("enabled sales AI requires consent_epoch >= 1")
        if self.enabled and not self.customer_notice_confirmed:
            raise ValueError("enabled sales AI requires confirmed customer notice")
        if self.enabled and self.data_mode is SalesAIDataMode.NO_CLOUD:
            raise ValueError("no_cloud mode cannot enable external sales AI")
        require_timezone_aware("updated_at", self.updated_at)
        canonical_labels(self.labels)
        if self.version is not None:
            self.version.validate()

    def normalized(self) -> "SalesAIConsentSnapshot":
        mode = self.data_mode if isinstance(self.data_mode, SalesAIDataMode) else SalesAIDataMode(str(self.data_mode))
        return replace(
            self,
            tenant_id=require_tenant_id(self.tenant_id),
            business_id=_business_id(self.business_id),
            provider=_provider(self.provider),
            base_url=_provider_base_url(self.base_url),
            data_mode=mode,
            consent_epoch=int(self.consent_epoch),
            labels=canonical_labels(self.labels),
        )

    def entity_id(self) -> str:
        return f"{require_tenant_id(self.tenant_id)}:{_business_id(self.business_id)}"

    def payload_for_versioning(self) -> dict[str, object]:
        normalized = self.normalized()
        return {
            "tenant_id": normalized.tenant_id,
            "business_id": normalized.business_id,
            "enabled": normalized.enabled,
            "provider": normalized.provider,
            "base_url": normalized.base_url,
            "data_mode": normalized.data_mode.value,
            "customer_notice_confirmed": normalized.customer_notice_confirmed,
            "consent_epoch": normalized.consent_epoch,
            "labels": dict(normalized.labels),
        }

    def with_version(self, *, version: ConfigVersion, updated_at: datetime) -> "SalesAIConsentSnapshot":
        return replace(self, version=version, updated_at=updated_at)

    def to_dict(self) -> dict[str, object]:
        normalized = self.normalized()
        normalized.validate()
        return {
            **normalized.payload_for_versioning(),
            "updated_at": normalized.updated_at.isoformat(),
            "version": None if normalized.version is None else normalized.version.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "SalesAIConsentSnapshot":
        item = dict(payload)
        raw_version = item.get("version")
        version = ConfigVersion.from_dict(dict(raw_version)) if isinstance(raw_version, Mapping) else None
        raw_updated = str(item.get("updated_at") or "").strip()
        updated_at = datetime.fromisoformat(raw_updated) if raw_updated else utc_now()
        snapshot = cls(
            tenant_id=str(item.get("tenant_id") or ""),
            business_id=str(item.get("business_id") or ""),
            enabled=bool(item.get("enabled", False)),
            provider=str(item.get("provider") or ""),
            base_url=str(item.get("base_url") or ""),
            data_mode=SalesAIDataMode(str(item.get("data_mode") or SalesAIDataMode.REDACTED.value)),
            customer_notice_confirmed=bool(item.get("customer_notice_confirmed", False)),
            consent_epoch=int(item.get("consent_epoch") or 0),
            updated_at=updated_at,
            labels=dict(item.get("labels") or {}),
            version=version,
        ).normalized()
        snapshot.validate()
        return snapshot


class SalesAIConsentStore:
    """Business-scoped, versioned consent owner for external Sales AI egress."""

    def __init__(self, backend: InMemoryVersionedConfigStore[SalesAIConsentSnapshot]) -> None:
        self._backend = backend

    @staticmethod
    def _key(tenant_id: str, business_id: str) -> str:
        return f"{require_tenant_id(tenant_id)}:{_business_id(business_id)}"

    def get(self, *, tenant_id: str, business_id: str) -> SalesAIConsentSnapshot | None:
        return self._backend._get_by_key(self._key(tenant_id, business_id))

    def configure(
        self,
        *,
        tenant_id: str,
        business_id: str,
        enabled: bool,
        provider: str,
        base_url: str,
        data_mode: SalesAIDataMode | str,
        customer_notice_confirmed: bool,
        actor: str,
        reason: str,
        expected_revision: int | None = None,
        labels: Mapping[str, str] | None = None,
    ) -> SalesAIConsentSnapshot:
        current = self.get(tenant_id=tenant_id, business_id=business_id)
        epoch = 1 if current is None else current.consent_epoch + 1
        snapshot = SalesAIConsentSnapshot(
            tenant_id=tenant_id,
            business_id=business_id,
            enabled=bool(enabled),
            provider=provider,
            base_url=base_url,
            data_mode=SalesAIDataMode(str(data_mode)),
            customer_notice_confirmed=bool(customer_notice_confirmed),
            consent_epoch=epoch,
            labels=dict(labels or {}),
        ).normalized()
        return self._backend._save_snapshot(
            snapshot,
            actor=actor,
            reason=reason,
            expected_revision=expected_revision,
        )


class PersistentSalesAIConsentStore(SalesAIConsentStore):
    def __init__(
        self,
        *,
        path: str | Path | None = None,
        audit_log_path: str | Path | None = None,
    ) -> None:
        store_path = Path(path) if path is not None else sales_ai_consent_store_path()
        audit_path = Path(audit_log_path) if audit_log_path is not None else sales_ai_consent_audit_log_path()
        backend = PersistentVersionedConfigStore(
            namespace="sales_ai_consent",
            snapshot_type=SalesAIConsentSnapshot,
            key_for_snapshot=lambda item: item.entity_id(),
            snapshot_from_dict=SalesAIConsentSnapshot.from_dict,
            audit_payload=lambda item: {
                "business_id": item.business_id,
                "enabled": item.enabled,
                "provider": item.provider,
                "base_url": item.base_url,
                "data_mode": item.data_mode.value,
                "customer_notice_confirmed": item.customer_notice_confirmed,
                "consent_epoch": item.consent_epoch,
            },
            path=store_path,
            audit_log_path=audit_path,
        )
        super().__init__(backend)

    def configure(self, **kwargs) -> SalesAIConsentSnapshot:
        current = self.get(tenant_id=kwargs["tenant_id"], business_id=kwargs["business_id"])
        epoch = 1 if current is None else current.consent_epoch + 1
        snapshot = SalesAIConsentSnapshot(
            tenant_id=kwargs["tenant_id"],
            business_id=kwargs["business_id"],
            enabled=bool(kwargs["enabled"]),
            provider=kwargs["provider"],
            base_url=kwargs["base_url"],
            data_mode=SalesAIDataMode(str(kwargs["data_mode"])),
            customer_notice_confirmed=bool(kwargs["customer_notice_confirmed"]),
            consent_epoch=epoch,
            labels=dict(kwargs.get("labels") or {}),
        ).normalized()
        return self._backend._save_persistent_snapshot(
            snapshot,
            actor=kwargs["actor"],
            reason=kwargs["reason"],
            expected_revision=kwargs.get("expected_revision"),
        )


@dataclass(frozen=True)
class SalesAIEgressPermit:
    tenant_id: str
    business_id: str
    consent_epoch: int
    provider: str
    base_url: str
    data_mode: SalesAIDataMode

    @property
    def provider_target(self) -> str:
        return f"{self.provider}|{self.base_url}"


def require_sales_ai_egress(
    consent: SalesAIConsentSnapshot | None,
    *,
    tenant_id: str,
    business_id: str,
    provider: str,
    base_url: str,
    expected_epoch: int | None = None,
) -> SalesAIEgressPermit:
    if consent is None:
        raise PermissionError("sales_ai_consent_missing")
    consent = consent.normalized()
    consent.validate()
    if consent.tenant_id != require_tenant_id(tenant_id) or consent.business_id != _business_id(business_id):
        raise PermissionError("sales_ai_consent_scope_mismatch")
    if not consent.enabled:
        raise PermissionError("sales_ai_consent_disabled")
    if consent.data_mode is SalesAIDataMode.NO_CLOUD:
        raise PermissionError("sales_ai_no_cloud")
    if not consent.customer_notice_confirmed:
        raise PermissionError("sales_ai_customer_notice_missing")
    requested_provider = _provider(provider)
    requested_base_url = _provider_base_url(base_url)
    if consent.provider != requested_provider or consent.base_url != requested_base_url:
        raise PermissionError("sales_ai_provider_target_changed")
    if expected_epoch is not None and consent.consent_epoch != int(expected_epoch):
        raise PermissionError("sales_ai_consent_epoch_changed")
    return SalesAIEgressPermit(
        tenant_id=consent.tenant_id,
        business_id=consent.business_id,
        consent_epoch=consent.consent_epoch,
        provider=consent.provider,
        base_url=consent.base_url,
        data_mode=consent.data_mode,
    )


def sales_ai_consent_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_SALES_AI_CONSENT_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "config" / "sales_ai_consent.json"


def sales_ai_consent_audit_log_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_SALES_AI_CONSENT_AUDIT_LOG_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "config" / "sales_ai_consent_audit.jsonl"


__all__ = [
    "DEFAULT_LLM_PROVIDER_POLICY",
    "LLMProviderPolicy",
    "PersistentSalesAIConsentStore",
    "SalesAIConsentSnapshot",
    "SalesAIConsentStore",
    "SalesAIDataMode",
    "SalesAIEgressPermit",
    "require_sales_ai_egress",
    "sales_ai_consent_audit_log_path",
    "sales_ai_consent_store_path",
]
