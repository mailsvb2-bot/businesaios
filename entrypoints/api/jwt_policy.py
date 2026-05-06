from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from governance.rbac_contract import RoleId
from entrypoints.api.auth_contract import AuthMechanism, AuthPrincipal, AuthVerdict, RequestAuthentication
from security.token_policy import TokenPolicy


CANON_API_JWT_POLICY = True
CANON_API_FINAL_OWNER = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode('ascii').rstrip('=')


def _b64url_decode(payload: str) -> bytes:
    text = str(payload)
    padding = '=' * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


@dataclass(frozen=True)
class JwtClaims:
    subject: str
    tenant_id: str
    audience: str | None = None
    actor_id: str | None = None
    session_id: str | None = None
    scopes: tuple[str, ...] = ()
    roles: tuple[RoleId, ...] = ()
    issued_at: datetime = field(default_factory=utc_now)
    expires_at: datetime = field(default_factory=lambda: utc_now() + timedelta(minutes=15))
    not_before: datetime | None = None
    token_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.subject or '').strip():
            raise ValueError('subject is required')
        if not str(self.tenant_id or '').strip():
            raise ValueError('tenant_id is required')
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError('jwt timestamps must be timezone-aware')
        if self.expires_at <= self.issued_at:
            raise ValueError('expires_at must be > issued_at')
        if self.not_before is not None and self.not_before.tzinfo is None:
            raise ValueError('not_before must be timezone-aware')

    def to_payload(self) -> dict[str, Any]:
        self.validate()
        return {
            'sub': self.subject,
            'tid': self.tenant_id,
            'aud': self.audience,
            'actor_id': self.actor_id,
            'sid': self.session_id,
            'scopes': list(self.scopes),
            'roles': [role.value for role in self.roles],
            'iat': int(self.issued_at.timestamp()),
            'exp': int(self.expires_at.timestamp()),
            'nbf': int(self.not_before.timestamp()) if self.not_before else None,
            'jti': self.token_id,
            'meta': dict(self.metadata),
        }


class JwtPolicy:
    algorithm = 'HS256'

    def __init__(
        self,
        *,
        secret: str,
        audience: str | None = None,
        issuer: str = 'businesaios-api',
        clock_skew_seconds: int = 30,
        max_ttl_seconds: int = 3600,
    ) -> None:
        self._secret = str(secret)
        if not self._secret:
            raise ValueError('secret is required')
        self._audience = audience
        self._issuer = str(issuer)
        self._clock_skew_seconds = int(clock_skew_seconds)
        self._token_policy = TokenPolicy(
            max_ttl_seconds=int(max_ttl_seconds),
            allow_clock_skew_seconds=int(clock_skew_seconds),
            require_subject=True,
            require_audience=audience is not None,
            require_issuer=True,
            require_session_id=False,
            allowed_algorithms=(self.algorithm,),
        )

    def issue(self, claims: JwtClaims) -> str:
        claims.validate()
        header = {'alg': self.algorithm, 'typ': 'JWT'}
        payload = claims.to_payload()
        payload['iss'] = self._issuer
        if payload.get('jti') is None:
            payload['jti'] = secrets.token_hex(8)
        encoded_header = _b64url_encode(json.dumps(header, separators=(',', ':'), sort_keys=True).encode('utf-8'))
        encoded_payload = _b64url_encode(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8'))
        signature = self._sign(f'{encoded_header}.{encoded_payload}'.encode('ascii'))
        return f'{encoded_header}.{encoded_payload}.{signature}'

    def authenticate(self, request: RequestAuthentication) -> AuthVerdict:
        request.validate()
        token = str(request.authorization or '').strip()
        if token.lower().startswith('bearer '):
            token = token[7:].strip()
        if not token:
            verdict = AuthVerdict(allowed=False, reason='missing_bearer_token', challenge='Bearer')
            verdict.validate()
            return verdict
        try:
            payload = self.decode(token)
        except ValueError as exc:
            verdict = AuthVerdict(allowed=False, reason=str(exc), mechanism=AuthMechanism.JWT, challenge='Bearer')
            verdict.validate()
            return verdict
        tenant_id = str(payload.get('tid') or '')
        if request.tenant_id and tenant_id and request.tenant_id != tenant_id:
            verdict = AuthVerdict(allowed=False, reason='tenant_mismatch', mechanism=AuthMechanism.JWT, challenge='Bearer')
            verdict.validate()
            return verdict
        principal = AuthPrincipal(
            subject=str(payload.get('sub') or ''),
            tenant_id=tenant_id or None,
            actor_id=str(payload.get('actor_id') or payload.get('sub') or ''),
            session_id=str(payload.get('sid') or '') or None,
            audience=str(payload.get('aud') or '') or None,
            roles=tuple(RoleId(str(item)) for item in (payload.get('roles') or [])),
            scopes=tuple(str(item) for item in (payload.get('scopes') or [])),
            metadata={
                'auth_type': 'jwt',
                'issuer': str(payload.get('iss') or ''),
                'token_id': str(payload.get('jti') or ''),
                'issued_at': datetime.fromtimestamp(int(payload.get('iat')), tz=timezone.utc).isoformat(),
                'expires_at': datetime.fromtimestamp(int(payload.get('exp')), tz=timezone.utc).isoformat(),
                'not_before': datetime.fromtimestamp(int(payload.get('nbf')), tz=timezone.utc).isoformat() if payload.get('nbf') is not None else None,
                'algorithm': self.algorithm,
                'session_created_at': datetime.fromtimestamp(int(payload.get('iat')), tz=timezone.utc).isoformat(),
                'metadata': dict(payload.get('meta') or {}),
            },
        )
        verdict = AuthVerdict(
            allowed=True,
            reason='authenticated',
            mechanism=AuthMechanism.JWT,
            principal=principal,
            labels={'issuer': str(payload.get('iss') or '')},
        )
        verdict.validate()
        return verdict

    def decode(self, token: str, *, now: datetime | None = None) -> dict[str, Any]:
        parts = str(token).split('.')
        if len(parts) != 3:
            raise ValueError('malformed_jwt')
        header_b64, payload_b64, sig_b64 = parts
        try:
            header = json.loads(_b64url_decode(header_b64).decode('utf-8'))
            payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))
        except Exception as exc:
            raise ValueError('invalid_jwt_encoding') from exc
        if header.get('alg') != self.algorithm:
            raise ValueError('unsupported_jwt_algorithm')
        if header.get('typ') != 'JWT':
            raise ValueError('invalid_jwt_type')
        expected_sig = self._sign(f'{header_b64}.{payload_b64}'.encode('ascii'))
        if not hmac.compare_digest(expected_sig, sig_b64):
            raise ValueError('bad_jwt_signature')
        moment = now or utc_now()
        if moment.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        issued_at = datetime.fromtimestamp(int(payload['iat']), tz=timezone.utc)
        expires_at = datetime.fromtimestamp(int(payload['exp']), tz=timezone.utc)
        not_before_raw = payload.get('nbf')
        not_before = datetime.fromtimestamp(int(not_before_raw), tz=timezone.utc) if not_before_raw is not None else None
        verdict = self._token_policy.evaluate(
            issued_at=issued_at,
            expires_at=expires_at,
            now=moment,
            scopes=tuple(str(item) for item in (payload.get('scopes') or [])),
            subject=str(payload.get('sub') or ''),
            audience=str(payload.get('aud') or '') or None,
            issuer=str(payload.get('iss') or '') or None,
            not_before=not_before,
            token_id=str(payload.get('jti') or '') or None,
            session_id=str(payload.get('sid') or '') or None,
            algorithm=str(header.get('alg') or ''),
            key_id=str(header.get('kid') or '') or None,
        )
        if not verdict.allowed:
            raise ValueError(f'jwt_{verdict.reason}')
        if payload.get('iss') != self._issuer:
            raise ValueError('unexpected_jwt_issuer')
        if self._audience is not None and payload.get('aud') != self._audience:
            raise ValueError('unexpected_jwt_audience')
        if not str(payload.get('tid') or '').strip():
            raise ValueError('missing_jwt_tenant')
        return payload

    def _sign(self, value: bytes) -> str:
        digest = hmac.new(self._secret.encode('utf-8'), value, hashlib.sha256).digest()
        return _b64url_encode(digest)


__all__ = [
    'CANON_API_JWT_POLICY',
    'JwtClaims',
    'JwtPolicy',
]
