from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

CANON_BUSINESS_AUTONOMY_SAFETY_CORE_WRAPPER = True
SAFETY_CORE_GOLDEN_FIXTURE_VERSION = "businessaios_safety_core_golden.v1"
RUST_SAFETY_CORE_MSRV = "1.75.0"
RUST_SAFETY_CORE_EDITION = "2021"
RUST_SAFETY_CORE_ALLOWED_DIRECT_DEPENDENCIES = ("serde", "serde_json")


class SafetyVerdictKind(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class SafetyRuntimePolicy:
    mode: str = "python_mirror"
    rust_available: bool = False

    @classmethod
    def python_mirror(cls) -> SafetyRuntimePolicy:
        return cls(mode="python_mirror", rust_available=False)

    @classmethod
    def strict_rust_required(cls, *, rust_available: bool = False) -> SafetyRuntimePolicy:
        return cls(mode="strict_rust_required", rust_available=bool(rust_available))

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, object] | None) -> SafetyRuntimePolicy:
        data = dict(metadata or {})
        mode = str(data.get("safety_core_mode") or "python_mirror").strip() or "python_mirror"
        rust_available = bool(data.get("rust_safety_core_available", False))
        if mode == "strict_rust_required":
            return cls.strict_rust_required(rust_available=rust_available)
        return cls.python_mirror()


def _policy_unavailable_verdict(policy: SafetyRuntimePolicy) -> SafetyVerdict | None:
    if policy.mode == "strict_rust_required" and not policy.rust_available:
        return SafetyVerdict.deny("rust_safety_core_unavailable", source="rust_safety_core_required")
    return None


@dataclass(frozen=True)
class SafetyVerdict:
    allowed: bool
    reason: str
    source: str = "python_safety_core"

    @classmethod
    def allow(cls, *, source: str = "python_safety_core") -> SafetyVerdict:
        return cls(True, "allow", source)

    @classmethod
    def deny(cls, reason: str, *, source: str = "python_safety_core") -> SafetyVerdict:
        return cls(False, str(reason or "safety_denied"), source)

    def to_metadata(self) -> dict[str, object]:
        return {"allowed": bool(self.allowed), "reason": self.reason, "source": self.source}


def validate_tenant_scope(*, tenant_id: str, business_id: str, binding_tenant_id: str, allow_global_fallback: bool = False, policy: SafetyRuntimePolicy | None = None) -> SafetyVerdict:
    runtime = policy or SafetyRuntimePolicy.python_mirror()
    unavailable = _policy_unavailable_verdict(runtime)
    if unavailable is not None:
        return unavailable
    tenant = str(tenant_id or "").strip()
    business = str(business_id or "").strip()
    binding = str(binding_tenant_id or "").strip()
    if not tenant:
        return SafetyVerdict.deny("tenant_id_required")
    if not business:
        return SafetyVerdict.deny("business_id_required")
    if tenant == "global" and not bool(allow_global_fallback):
        return SafetyVerdict.deny("global_tenant_forbidden")
    if not binding:
        return SafetyVerdict.deny("tenant_binding_required")
    if tenant != binding:
        return SafetyVerdict.deny("tenant_binding_mismatch")
    return SafetyVerdict.allow()


def _money_amount(amount_minor: object, currency: object) -> SafetyVerdict:
    currency_value = str(currency or "").strip()
    if not currency_value:
        return SafetyVerdict.deny("currency_required")
    try:
        amount = int(amount_minor)
    except (TypeError, ValueError):
        return SafetyVerdict.deny("invalid_money_minor_units")
    if amount < 0:
        return SafetyVerdict.deny("negative_amount_forbidden")
    return SafetyVerdict.allow()


def validate_budget(*, estimated_minor: object, limit_minor: object, currency: object = "RUB", limit_currency: object | None = None, policy: SafetyRuntimePolicy | None = None) -> SafetyVerdict:
    runtime = policy or SafetyRuntimePolicy.python_mirror()
    unavailable = _policy_unavailable_verdict(runtime)
    if unavailable is not None:
        return unavailable
    estimated_currency = str(currency or "").strip()
    approved_currency = str(limit_currency if limit_currency is not None else currency or "").strip()
    estimated_valid = _money_amount(estimated_minor, estimated_currency)
    if not estimated_valid.allowed:
        return estimated_valid
    limit_valid = _money_amount(limit_minor, approved_currency)
    if not limit_valid.allowed:
        return limit_valid
    if estimated_currency != approved_currency:
        return SafetyVerdict.deny("currency_mismatch")
    if int(estimated_minor) > int(limit_minor):
        return SafetyVerdict.deny("budget_exceeded")
    return SafetyVerdict.allow()


def validate_refund(*, captured_minor: object, refund_minor: object, currency: object = "RUB", policy: SafetyRuntimePolicy | None = None) -> SafetyVerdict:
    result = validate_budget(estimated_minor=refund_minor, limit_minor=captured_minor, currency=currency, policy=policy)
    if not result.allowed and result.reason == "budget_exceeded":
        return SafetyVerdict.deny("refund_exceeds_captured")
    return result


def validate_blast_radius(*, requested_outbound: object, approved_limit: object, policy: SafetyRuntimePolicy | None = None) -> SafetyVerdict:
    runtime = policy or SafetyRuntimePolicy.python_mirror()
    unavailable = _policy_unavailable_verdict(runtime)
    if unavailable is not None:
        return unavailable
    try:
        requested = int(requested_outbound)
        limit = int(approved_limit)
    except (TypeError, ValueError):
        return SafetyVerdict.deny("invalid_blast_radius_units")
    if limit <= 0:
        return SafetyVerdict.deny("blast_radius_limit_required")
    if requested > limit:
        return SafetyVerdict.deny("blast_radius_exceeded")
    return SafetyVerdict.allow()


_ALLOWED_IDEMPOTENCY_TRANSITIONS = {
    ("new", "reserved"),
    ("reserved", "committed"),
    ("reserved", "failed_retryable"),
    ("reserved", "failed_final"),
}


def validate_idempotency_transition(*, from_state: str, to_state: str, policy: SafetyRuntimePolicy | None = None) -> SafetyVerdict:
    runtime = policy or SafetyRuntimePolicy.python_mirror()
    unavailable = _policy_unavailable_verdict(runtime)
    if unavailable is not None:
        return unavailable
    pair = (str(from_state or "").strip(), str(to_state or "").strip())
    if pair in _ALLOWED_IDEMPOTENCY_TRANSITIONS:
        return SafetyVerdict.allow()
    if pair == ("committed", "committed"):
        return SafetyVerdict.deny("duplicate_committed_execution")
    if pair[0] == "failed_final" and pair[1] in {"reserved", "committed"}:
        return SafetyVerdict.deny("final_failure_retry_forbidden")
    return SafetyVerdict.deny("invalid_idempotency_transition")


_ALLOWED_OUTBOX_TRANSITIONS = {
    ("pending", "sent"),
    ("pending", "cancelled"),
    ("sent", "verified"),
    ("sent", "failed_retryable"),
    ("failed_retryable", "sent"),
    ("failed_retryable", "failed_final"),
}


def validate_outbox_transition(*, from_state: str, to_state: str, policy: SafetyRuntimePolicy | None = None) -> SafetyVerdict:
    runtime = policy or SafetyRuntimePolicy.python_mirror()
    unavailable = _policy_unavailable_verdict(runtime)
    if unavailable is not None:
        return unavailable
    pair = (str(from_state or "").strip(), str(to_state or "").strip())
    if pair in _ALLOWED_OUTBOX_TRANSITIONS:
        return SafetyVerdict.allow()
    if pair in {("verified", "pending"), ("verified", "sent"), ("failed_final", "sent"), ("cancelled", "sent")}:
        return SafetyVerdict.deny("terminal_outbox_transition_forbidden")
    return SafetyVerdict.deny("invalid_outbox_transition")


def evaluate_golden_case(case: Mapping[str, object], *, policy: SafetyRuntimePolicy | None = None) -> SafetyVerdict:
    kind = str(case.get("kind") or "").strip()
    raw_input = case.get("input")
    if not isinstance(raw_input, Mapping):
        return SafetyVerdict.deny("invalid_fixture_input")
    data = dict(raw_input)
    if kind == "tenant_scope":
        return validate_tenant_scope(
            tenant_id=str(data.get("tenant_id") or ""),
            business_id=str(data.get("business_id") or ""),
            binding_tenant_id=str(data.get("binding_tenant_id") or ""),
            allow_global_fallback=bool(data.get("allow_global_fallback", False)),
            policy=policy,
        )
    if kind == "budget":
        return validate_budget(
            estimated_minor=data.get("estimated_minor"),
            limit_minor=data.get("limit_minor"),
            currency=data.get("currency", "RUB"),
            limit_currency=data.get("limit_currency"),
            policy=policy,
        )
    if kind == "refund":
        return validate_refund(captured_minor=data.get("captured_minor"), refund_minor=data.get("refund_minor"), currency=data.get("currency", "RUB"), policy=policy)
    if kind == "blast_radius":
        return validate_blast_radius(requested_outbound=data.get("requested_outbound"), approved_limit=data.get("approved_limit"), policy=policy)
    if kind == "idempotency_transition":
        return validate_idempotency_transition(from_state=str(data.get("from") or ""), to_state=str(data.get("to") or ""), policy=policy)
    if kind == "outbox_transition":
        return validate_outbox_transition(from_state=str(data.get("from") or ""), to_state=str(data.get("to") or ""), policy=policy)
    return SafetyVerdict.deny("unknown_fixture_kind")


def build_safety_core_admin_surface(*, rust_available: bool = False, mode: str = "python_mirror", parity_checked: bool = False, drift_detected: bool = False, parity_artifact_path: str = "artifacts/ci/safety_core_parity.json", supply_chain_artifact_path: str = "artifacts/ci/rust_supply_chain.json") -> dict[str, object]:
    strict = SafetyRuntimePolicy.strict_rust_required(rust_available=rust_available)
    strict_verdict = validate_budget(estimated_minor=1, limit_minor=1, policy=strict)
    return {
        "surface": "business_autonomy_safety_core",
        "mode": str(mode or "python_mirror"),
        "rust_available": bool(rust_available),
        "runtime_policy": "fail_closed",
        "decision_core_replaced": False,
        "ffi_enabled": False,
        "msrv": RUST_SAFETY_CORE_MSRV,
        "rust_edition": RUST_SAFETY_CORE_EDITION,
        "dependency_policy": "allowlist",
        "allowed_direct_dependencies": list(RUST_SAFETY_CORE_ALLOWED_DIRECT_DEPENDENCIES),
        "guards": ["budget", "blast_radius", "tenant_scope", "idempotency_transition", "outbox_transition", "refund", "write_action", "paid_action", "campaign_scope"],
        "strict_rust_required_verdict": strict_verdict.to_metadata(),
        "golden_fixture_version": SAFETY_CORE_GOLDEN_FIXTURE_VERSION,
        "live_contract_version": "businessaios_safety_live_contract_golden.v1",
        "python_wrapper_version": "business_autonomy_safety_core_wrapper.v1",
        "rust_fixture_runner_required": True,
        "parity_checked": bool(parity_checked),
        "drift_detected": bool(drift_detected),
        "parity_artifact_path": parity_artifact_path,
        "supply_chain_artifact_path": supply_chain_artifact_path,
        "supply_chain_checked": True,
        "rust_diagnostic_bridge": "cli_only_admin_diagnostics",
        "admin_visibility": True,
    }


__all__ = [
    "CANON_BUSINESS_AUTONOMY_SAFETY_CORE_WRAPPER",
    "SAFETY_CORE_GOLDEN_FIXTURE_VERSION",
    "RUST_SAFETY_CORE_ALLOWED_DIRECT_DEPENDENCIES",
    "RUST_SAFETY_CORE_EDITION",
    "RUST_SAFETY_CORE_MSRV",
    "SafetyRuntimePolicy",
    "SafetyVerdict",
    "SafetyVerdictKind",
    "build_safety_core_admin_surface",
    "evaluate_golden_case",
    "validate_blast_radius",
    "validate_budget",
    "validate_idempotency_transition",
    "validate_outbox_transition",
    "validate_refund",
    "validate_tenant_scope",
]
