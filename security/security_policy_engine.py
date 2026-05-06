from __future__ import annotations

"""Canonical security policy engine.

This is a security gate, not a sovereign business decision-maker.
It evaluates token/session/access/compliance/fraud constraints and emits a
fail-closed verdict plus evidence for audit.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from governance.rbac_contract import ActorContext
from security.access_policy import DataAccessPolicy, SecurityAction, SecurityResource
from security.compliance_engine import ComplianceEngine, ComplianceVerdict
from security.fraud_detection_engine import FraudDetectionEngine, FraudVerdict
from security.session_policy import SessionPolicy, SessionVerdict
from security.token_policy import TokenPolicy, TokenVerdict


CANON_SECURITY_POLICY_ENGINE = True


@dataclass(frozen=True)
class SecurityEvaluationResult:
    allowed: bool
    reason: str
    token: TokenVerdict
    session: SessionVerdict
    access_allowed: bool
    compliance: ComplianceVerdict
    fraud: FraudVerdict
    operator_required: bool
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass
class SecurityPolicyEngine:
    token_policy: TokenPolicy = field(default_factory=TokenPolicy)
    session_policy: SessionPolicy = field(default_factory=SessionPolicy)
    access_policy: DataAccessPolicy = field(default_factory=DataAccessPolicy)
    compliance_engine: ComplianceEngine = field(default_factory=ComplianceEngine)
    fraud_engine: FraudDetectionEngine = field(default_factory=FraudDetectionEngine)

    def evaluate(
        self,
        *,
        actor: ActorContext,
        resource: SecurityResource,
        action: SecurityAction,
        auth_payload: Mapping[str, Any],
        session_payload: Mapping[str, Any],
        transport_encrypted: bool,
        compliance_evidence: Mapping[str, object],
        fraud_signals: Mapping[str, float | int | bool],
        now: datetime | None = None,
    ) -> SecurityEvaluationResult:
        evaluation_now = now or datetime.now(timezone.utc)
        token_verdict = self.token_policy.evaluate(
            issued_at=self._parse_dt(auth_payload.get('issued_at'), fallback=evaluation_now),
            expires_at=self._parse_dt(auth_payload.get('expires_at'), fallback=evaluation_now),
            now=self._parse_dt(auth_payload.get('now'), fallback=evaluation_now),
            scopes=self._normalize_scopes(auth_payload.get('scopes')),
            subject=self._opt_text(auth_payload.get('subject')),
            audience=self._opt_text(auth_payload.get('audience')),
            issuer=self._opt_text(auth_payload.get('issuer')),
            not_before=self._parse_dt(auth_payload.get('not_before'), fallback=None),
            token_id=self._opt_text(auth_payload.get('token_id')),
            session_id=self._opt_text(auth_payload.get('session_id')),
            algorithm=self._opt_text(auth_payload.get('algorithm')),
            key_id=self._opt_text(auth_payload.get('key_id')),
        )
        session_verdict = self.session_policy.evaluate(
            created_at=self._required_dt(session_payload.get('created_at') or session_payload.get('issued_at')),
            last_seen_at=self._required_dt(session_payload.get('last_seen_at') or session_payload.get('expires_at')),
            now=self._parse_dt(session_payload.get('now'), fallback=evaluation_now),
            expected_ip=self._binding_value(session_payload, auth_payload, 'expected_ip'),
            observed_ip=self._binding_value(session_payload, auth_payload, 'observed_ip'),
            expected_user_agent=self._binding_value(session_payload, auth_payload, 'expected_user_agent'),
            observed_user_agent=self._binding_value(session_payload, auth_payload, 'observed_user_agent'),
            revoked_at=self._parse_dt(session_payload.get('revoked_at'), fallback=None),
            auth_level=self._opt_text(session_payload.get('auth_level') or auth_payload.get('auth_level')),
            mfa_verified_at=self._parse_dt(session_payload.get('mfa_verified_at'), fallback=None),
        )
        binding_reason = self._validate_binding_contract(auth_payload=auth_payload, session_payload=session_payload)
        access_verdict = self.access_policy.evaluate(
            actor=actor,
            action=action,
            resource=resource,
            transport_encrypted=transport_encrypted,
            metadata={'surface': 'security_policy_engine'},
        )
        compliance_verdict = self.compliance_engine.evaluate(compliance_evidence)
        fraud_verdict = self.fraud_engine.evaluate(tenant_id=actor.tenant_id, signals=fraud_signals)
        evidence = {
            'token_reason': token_verdict.reason,
            'session_reason': session_verdict.reason,
            'access_reason': access_verdict.reason,
            'compliance_score': compliance_verdict.score,
            'fraud_score': fraud_verdict.risk_score,
            'classification': resource.classification.category.value,
            'sensitivity': resource.classification.sensitivity.value,
            'binding_reason': binding_reason or 'ok',
        }
        operator_required = bool(
            access_verdict.operator_required
            or fraud_verdict.requires_operator
            or access_verdict.reason == 'high_sensitivity_export_requires_operator'
        )
        if not token_verdict.allowed:
            return SecurityEvaluationResult(False, token_verdict.reason, token_verdict, session_verdict, access_verdict.allowed, compliance_verdict, fraud_verdict, operator_required, evidence)
        if not session_verdict.allowed:
            return SecurityEvaluationResult(False, session_verdict.reason, token_verdict, session_verdict, access_verdict.allowed, compliance_verdict, fraud_verdict, operator_required, evidence)
        if binding_reason is not None:
            return SecurityEvaluationResult(False, binding_reason, token_verdict, session_verdict, access_verdict.allowed, compliance_verdict, fraud_verdict, True, evidence)
        if not access_verdict.allowed:
            return SecurityEvaluationResult(False, access_verdict.reason, token_verdict, session_verdict, access_verdict.allowed, compliance_verdict, fraud_verdict, operator_required, evidence)
        if not compliance_verdict.compliant:
            return SecurityEvaluationResult(False, 'compliance_failed', token_verdict, session_verdict, access_verdict.allowed, compliance_verdict, fraud_verdict, True, evidence)
        if not fraud_verdict.allowed:
            return SecurityEvaluationResult(False, fraud_verdict.reason, token_verdict, session_verdict, access_verdict.allowed, compliance_verdict, fraud_verdict, True, evidence)
        return SecurityEvaluationResult(True, 'allowed', token_verdict, session_verdict, access_verdict.allowed, compliance_verdict, fraud_verdict, operator_required, evidence)

    @staticmethod
    def _normalize_scopes(value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            raw = value.replace(',', ' ').split()
        elif isinstance(value, (list, tuple, set)):
            raw = [str(item) for item in value]
        else:
            raw = []
        result: list[str] = []
        for item in raw:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return tuple(result)

    @staticmethod
    def _opt_text(value: Any) -> str | None:
        text = str(value or '').strip()
        return text or None

    @staticmethod
    def _parse_dt(value: Any, *, fallback: datetime | None) -> datetime | None:
        if value is None:
            return fallback
        text = str(value or '').strip()
        if not text:
            return fallback
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @classmethod
    def _required_dt(cls, value: Any) -> datetime:
        parsed = cls._parse_dt(value, fallback=None)
        if parsed is None:
            raise ValueError('required timestamp is missing')
        return parsed

    @classmethod
    def _binding_value(cls, session_payload: Mapping[str, Any], auth_payload: Mapping[str, Any], field_name: str) -> str | None:
        session_value = cls._opt_text(session_payload.get(field_name))
        auth_value = cls._opt_text(auth_payload.get(field_name))
        return session_value or auth_value

    @classmethod
    def _validate_binding_contract(cls, *, auth_payload: Mapping[str, Any], session_payload: Mapping[str, Any]) -> str | None:
        binding_pairs = (
            ('expected_ip', 'observed_ip'),
            ('expected_user_agent', 'observed_user_agent'),
        )
        for expected_key, observed_key in binding_pairs:
            expected = cls._binding_value(session_payload, auth_payload, expected_key)
            observed = cls._binding_value(session_payload, auth_payload, observed_key)
            # Observed request metadata without an explicit bound expectation is normal.
            # Fail closed only when a token/session declares binding evidence but the
            # corresponding request observation is missing or mismatched.
            if expected and not observed:
                return f'partial_binding_evidence:{expected_key}'
            if expected and observed and expected != observed:
                suffix = 'ip' if 'ip' in expected_key else 'user_agent'
                return f'{suffix}_mismatch'
        return None


__all__ = [
    'CANON_SECURITY_POLICY_ENGINE',
    'SecurityEvaluationResult',
    'SecurityPolicyEngine',
]
