from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC

from compliance.data_classification import KeywordDataClassifier
from governance.rbac_contract import ActorContext, RoleId
from security.access_policy import SecurityAction, SecurityResource
from security.security_policy_engine import SecurityPolicyEngine


def _resource() -> SecurityResource:
    classifier = KeywordDataClassifier()
    classification = classifier.classify_payload if False else None
    result = classifier.classify(
        __import__('compliance.data_classification', fromlist=['DataAsset']).DataAsset(
            asset_id='a1',
            name='customer internal dashboard',
            content_type='text/html',
            tags=('internal',),
            metadata={},
            source_system='web',
            region_hint='eu',
        )
    )
    return SecurityResource(
        resource_type='web_console',
        resource_id='admin',
        tenant_id='tenant-1',
        classification=result,
        encryption_required=False,
    )


def test_security_policy_engine_allows_happy_path() -> None:
    now = datetime.now(UTC)
    engine = SecurityPolicyEngine()
    actor = ActorContext(actor_id='owner-1', tenant_id='tenant-1', role_ids=frozenset({RoleId.OWNER}))
    verdict = engine.evaluate(
        actor=actor,
        resource=_resource(),
        action=SecurityAction.READ,
        auth_payload={
            'issued_at': (now - timedelta(minutes=5)).isoformat(),
            'expires_at': (now + timedelta(minutes=30)).isoformat(),
            'subject': 'owner-1',
            'audience': 'web',
        },
        session_payload={
            'created_at': (now - timedelta(minutes=15)).isoformat(),
            'last_seen_at': (now - timedelta(minutes=1)).isoformat(),
        },
        transport_encrypted=True,
        compliance_evidence={
            'encryption_at_rest': True,
            'encryption_in_transit': True,
            'immutable_audit_log': True,
            'rbac_enforced': True,
            'session_policy_enforced': True,
            'token_policy_enforced': True,
            'secret_rotation': True,
            'fraud_monitoring': True,
        },
        fraud_signals={'request_rate': 1.0},
        now=now,
    )
    assert verdict.allowed is True
    assert verdict.reason == 'allowed'


def test_security_policy_engine_fails_closed_on_partial_binding_evidence() -> None:
    now = datetime.now(UTC)
    engine = SecurityPolicyEngine()
    actor = ActorContext(actor_id='owner-1', tenant_id='tenant-1', role_ids=frozenset({RoleId.OWNER}))
    verdict = engine.evaluate(
        actor=actor,
        resource=_resource(),
        action=SecurityAction.READ,
        auth_payload={
            'issued_at': (now - timedelta(minutes=5)).isoformat(),
            'expires_at': (now + timedelta(minutes=30)).isoformat(),
            'subject': 'owner-1',
            'audience': 'web',
            'expected_ip': '10.0.0.1',
        },
        session_payload={
            'created_at': (now - timedelta(minutes=15)).isoformat(),
            'last_seen_at': (now - timedelta(minutes=1)).isoformat(),
        },
        transport_encrypted=True,
        compliance_evidence={
            'encryption_at_rest': True,
            'encryption_in_transit': True,
            'immutable_audit_log': True,
            'rbac_enforced': True,
            'session_policy_enforced': True,
            'token_policy_enforced': True,
            'secret_rotation': True,
            'fraud_monitoring': True,
        },
        fraud_signals={'request_rate': 1.0},
        now=now,
    )
    assert verdict.allowed is False
    assert verdict.reason.startswith('partial_binding_evidence')
