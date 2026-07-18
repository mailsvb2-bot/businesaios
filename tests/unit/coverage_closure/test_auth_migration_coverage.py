from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from deployment.migration_guard import (
    MigrationGuard,
    MigrationGuardError,
    MigrationGuardPolicy,
    MigrationRecord,
    _migration_version,
)
from entrypoints.api import api_key_policy as api_module
from entrypoints.api.api_key_policy import (
    ApiKeyPolicy,
    ApiKeyRecord,
    InMemoryApiKeyStore,
    PersistentApiKeyStore,
    _derive_secret_hash,
    api_key_store_path,
    build_default_api_key_store,
)
from entrypoints.api.auth_contract import RequestAuthentication
from entrypoints.api.jwt_policy import JwtClaims, JwtPolicy, _b64url_encode
from governance.rbac_contract import RoleId


def test_migration_guard_policy_and_registry_contracts() -> None:
    with pytest.raises(ValueError):
        MigrationRecord(0, "x")
    with pytest.raises(ValueError):
        MigrationRecord(1, "")
    with pytest.raises(ValueError):
        MigrationGuardPolicy(max_linear_jump=-1)

    strict = MigrationGuardPolicy(max_linear_jump=1)
    bad = strict.evaluate(current_version=-1, target_version=-2, pending_versions=(2, 1, 1))
    assert bad.blocked
    text = " ".join(bad.reasons)
    assert "must be >= 0" in text and "not sorted" in text and "duplicates" in text

    regression = strict.evaluate(current_version=3, target_version=2, pending_versions=())
    assert any("lower than current" in reason for reason in regression.reasons)
    empty = strict.evaluate(current_version=1, target_version=2, pending_versions=())
    assert any("pending migrations are empty" in reason for reason in empty.reasons)
    non_contiguous = strict.evaluate(current_version=1, target_version=3, pending_versions=(3,))
    assert any("not contiguous" in reason for reason in non_contiguous.reasons)
    assert any("jump too large" in reason for reason in non_contiguous.reasons)

    permissive = MigrationGuardPolicy(allow_major_jump_without_approval=True, max_linear_jump=0)
    assert not permissive.evaluate(current_version=1, target_version=3, pending_versions=(2, 3)).blocked
    assert not MigrationGuardPolicy(allow_version_regression=True).evaluate(current_version=2, target_version=1, pending_versions=()).blocked

    assert _migration_version({"version": 4}) == 4
    assert _migration_version(MigrationRecord(5, "five")) == 5

    class Registry:
        def __init__(self, pending):
            self._pending = pending

        def current_version(self, _executor, *, scope, component):
            assert scope == "storage" and component == "storage_migrations"
            return 1

        def latest_version(self):
            return 3

        def pending(self, current_version):
            assert current_version == 1
            return self._pending

    guard = MigrationGuard(policy=permissive)
    safe = guard.assess(registry=Registry((MigrationRecord(3, "three"), {"version": 2})), executor=object())
    assert safe.pending_versions == (2, 3) and not safe.blocked
    assert guard.assert_safe_to_deploy(registry=Registry(({"version": 2}, {"version": 3})), executor=object()) == safe

    blocked_guard = MigrationGuard(policy=MigrationGuardPolicy(max_linear_jump=0))
    with pytest.raises(MigrationGuardError, match="blocked release"):
        blocked_guard.assert_safe_to_deploy(registry=Registry(({"version": 2}, {"version": 3})), executor=object())


def test_api_key_records_stores_persistence_and_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="secret is required"):
        _derive_secret_hash(secret="")
    digest = _derive_secret_hash(secret="raw", pepper="pep")
    assert len(digest) == 64

    now = datetime.now(UTC)
    base = dict(key_id="id", secret_hash=digest, tenant_id="tenant", subject="svc", created_at=now)
    for field in ("key_id", "secret_hash", "tenant_id", "subject"):
        values = dict(base)
        values[field] = ""
        with pytest.raises(ValueError):
            ApiKeyRecord(**values).validate()
    with pytest.raises(ValueError, match="created_at"):
        ApiKeyRecord(**{**base, "created_at": datetime.now()}).validate()
    with pytest.raises(ValueError, match="expires_at"):
        ApiKeyRecord(**base, expires_at=datetime.now()).validate()
    with pytest.raises(ValueError, match="revoked_at"):
        ApiKeyRecord(**base, revoked_at=datetime.now()).validate()

    active = ApiKeyRecord(**base, expires_at=now + timedelta(minutes=1))
    active.validate()
    assert active.is_active(now=now)
    assert not ApiKeyRecord(**base, expires_at=now).is_active(now=now)
    assert not ApiKeyRecord(**base, revoked_at=now).is_active(now=now)
    with pytest.raises(ValueError, match="timezone-aware"):
        active.is_active(now=datetime.now())

    monkeypatch.setattr(api_module.secrets, "token_urlsafe", lambda _n: "secret")
    monkeypatch.setattr(api_module.secrets, "token_hex", lambda _n: "abc123")
    store = InMemoryApiKeyStore(pepper="pep")
    record, token = store.issue(
        tenant_id="tenant",
        subject="svc",
        actor_id="actor",
        roles=(RoleId.SYSTEM,),
        scopes=("read",),
        display_name="Service",
        ttl_seconds=120,
        metadata={"owner": "test"},
    )
    assert token == "ak_abc123.secret"
    assert store.pepper == "pep" and store.get(record.key_id) == record
    assert store.verify_secret(key_id=record.key_id, raw_secret="secret")
    assert not store.verify_secret(key_id="unknown", raw_secret="secret")
    assert not store.verify_secret(key_id=record.key_id, raw_secret="wrong")

    auth = ApiKeyPolicy(store=store)
    assert auth.authenticate(RequestAuthentication()).reason == "missing_api_key"
    assert auth.authenticate(RequestAuthentication(api_key="bad")).reason == "malformed_api_key"
    assert auth.authenticate(RequestAuthentication(api_key="unknown.secret")).reason == "unknown_api_key"
    assert auth.authenticate(RequestAuthentication(api_key=token, tenant_id="other")).reason == "tenant_mismatch"
    assert auth.authenticate(RequestAuthentication(api_key=f"{record.key_id}.wrong")).reason == "bad_api_key_secret"
    good = auth.authenticate(RequestAuthentication(api_key=token, tenant_id="tenant"))
    assert good.allowed and good.principal.subject == "svc"
    assert good.principal.metadata["owner"] == "test"

    revoked = store.revoke(record.key_id, at=now)
    assert revoked.revoked_at == now
    assert auth.authenticate(RequestAuthentication(api_key=token)).reason == "inactive_api_key"

    path = tmp_path / "keys.json"
    persisted = PersistentApiKeyStore(pepper="pep", path=path)
    saved = ApiKeyRecord(
        key_id="saved",
        secret_hash=_derive_secret_hash(secret="x", pepper="pep"),
        tenant_id="tenant",
        subject="saved",
    )
    persisted.register(saved)
    assert path.exists()
    reloaded = PersistentApiKeyStore(pepper="pep", path=path)
    assert reloaded.get("saved") is not None
    reloaded.revoke("saved", at=now)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["records"][0]["revoked_at"] is not None

    monkeypatch.setenv("BUSINESAIOS_API_KEY_STORE_PATH", str(tmp_path / "explicit.json"))
    assert api_key_store_path() == tmp_path / "explicit.json"
    monkeypatch.delenv("BUSINESAIOS_API_KEY_STORE_PATH")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    assert api_key_store_path() == tmp_path / "data/api/api_keys.json"
    monkeypatch.setenv("BUSINESAIOS_API_KEY_STORE_BACKEND", "memory")
    assert isinstance(build_default_api_key_store(), InMemoryApiKeyStore)
    monkeypatch.setenv("BUSINESAIOS_API_KEY_STORE_BACKEND", "file")
    assert isinstance(build_default_api_key_store(), PersistentApiKeyStore)


def _manual_token(policy: JwtPolicy, header: dict, payload: dict, *, sign: bool = True) -> str:
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = policy._sign(f"{header_b64}.{payload_b64}".encode("ascii")) if sign else "bad"
    return f"{header_b64}.{payload_b64}.{sig}"


def test_jwt_claims_issue_decode_and_authentication_matrix() -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    with pytest.raises(ValueError):
        JwtPolicy(secret="")
    with pytest.raises(ValueError, match="subject"):
        JwtClaims("", "t", issued_at=now, expires_at=now + timedelta(minutes=1)).validate()
    with pytest.raises(ValueError, match="tenant"):
        JwtClaims("s", "", issued_at=now, expires_at=now + timedelta(minutes=1)).validate()
    with pytest.raises(ValueError, match="timezone-aware"):
        JwtClaims("s", "t", issued_at=datetime.now(), expires_at=datetime.now() + timedelta(minutes=1)).validate()
    with pytest.raises(ValueError, match="expires_at"):
        JwtClaims("s", "t", issued_at=now, expires_at=now).validate()
    with pytest.raises(ValueError, match="not_before"):
        JwtClaims(
            "s",
            "t",
            issued_at=now,
            expires_at=now + timedelta(minutes=1),
            not_before=datetime.now(),
        ).validate()

    policy = JwtPolicy(secret="secret", audience="api", issuer="issuer", max_ttl_seconds=600, clock_skew_seconds=0)
    claims = JwtClaims(
        subject="user",
        tenant_id="tenant",
        audience="api",
        actor_id="actor",
        session_id="session",
        scopes=("read",),
        roles=(RoleId.OWNER,),
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        not_before=now,
        token_id="token",
        metadata={"x": 1},
    )
    payload = claims.to_payload()
    assert payload["sub"] == "user" and payload["roles"] == ["owner"]
    token = policy.issue(claims)
    decoded = policy.decode(token, now=now + timedelta(seconds=1))
    assert decoded["tid"] == "tenant"
    assert policy.authenticate(RequestAuthentication()).reason == "missing_bearer_token"
    malformed = policy.authenticate(RequestAuthentication(authorization="Bearer bad"))
    assert malformed.reason == "malformed_jwt"
    mismatch = policy.authenticate(RequestAuthentication(authorization=token, tenant_id="other"))
    assert mismatch.reason == "tenant_mismatch"
    good = policy.authenticate(RequestAuthentication(authorization=f"Bearer {token}", tenant_id="tenant"))
    assert good.allowed and good.principal.actor_id == "actor"
    assert good.principal.metadata["metadata"] == {"x": 1}

    with pytest.raises(ValueError, match="malformed_jwt"):
        policy.decode("one.two")
    with pytest.raises(ValueError, match="invalid_jwt_encoding"):
        policy.decode("bad.bad.bad")

    common = {
        "sub": "user",
        "tid": "tenant",
        "aud": "api",
        "iss": "issuer",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "scopes": [],
        "roles": [],
        "meta": {},
    }
    with pytest.raises(ValueError, match="unsupported_jwt_algorithm"):
        policy.decode(_manual_token(policy, {"alg": "none", "typ": "JWT"}, common), now=now)
    with pytest.raises(ValueError, match="invalid_jwt_type"):
        policy.decode(_manual_token(policy, {"alg": "HS256", "typ": "OTHER"}, common), now=now)
    with pytest.raises(ValueError, match="bad_jwt_signature"):
        policy.decode(_manual_token(policy, {"alg": "HS256", "typ": "JWT"}, common, sign=False), now=now)
    with pytest.raises(ValueError, match="timezone-aware"):
        policy.decode(token, now=datetime.now())

    for changed, reason in [
        ({"iss": "other"}, "unexpected_jwt_issuer"),
        ({"aud": "other"}, "jwt_missing_audience|unexpected_jwt_audience"),
        ({"tid": ""}, "missing_jwt_tenant"),
        ({"exp": int((now - timedelta(seconds=1)).timestamp())}, "jwt_invalid_lifetime|jwt_expired"),
        (
            {
                "iat": int((now + timedelta(minutes=1)).timestamp()),
                "exp": int((now + timedelta(minutes=2)).timestamp()),
            },
            "jwt_used_before_issue_time",
        ),
        ({"nbf": int((now + timedelta(minutes=1)).timestamp())}, "jwt_not_before_violation"),
    ]:
        body = {**common, **changed}
        with pytest.raises(ValueError, match=reason):
            policy.decode(_manual_token(policy, {"alg": "HS256", "typ": "JWT"}, body), now=now)
