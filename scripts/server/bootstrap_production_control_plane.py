from __future__ import annotations

import argparse
import contextlib
import os
import re
import shlex
import stat
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from entrypoints.api.api_key_policy import (
    ApiKeyRecord,
    PersistentApiKeyStore,
    build_default_api_key_store,
)
from governance.persistence_codec import exclusive_file_lock
from governance.rbac_contract import RoleId
from runtime.governance.pricing_versioning import validate_explicit_pricing_version
from tenancy.tenant_registry import PersistentTenantRegistry, build_default_tenant_registry

CANON_PRODUCTION_CONTROL_PLANE_BOOTSTRAP = True

CANONICAL_PRODUCTION_ENV_FILE = Path("/etc/businesaios/api.env")
DEFAULT_ENV_FILE = CANONICAL_PRODUCTION_ENV_FILE
CANONICAL_RUNTIME_BINDINGS: dict[str, str] = {
    "PRODUCTION_STRICT_MODE": "1",
    "DATA_DIR": "/var/lib/businesaios/runtime",
    "PRICING_FINGERPRINT_PATH": "/var/lib/businesaios/runtime/governance/pricing_fingerprint.json",
    "BUSINESAIOS_TENANT_REGISTRY_BACKEND": "file",
    "BUSINESAIOS_TENANT_REGISTRY_PATH": "/var/lib/businesaios/runtime/tenancy/tenant_registry.json",
    "BUSINESAIOS_TENANT_POLICY_STORE_BACKEND": "file",
    "BUSINESAIOS_TENANT_POLICY_STORE_PATH": "/var/lib/businesaios/runtime/tenancy/tenant_policies.json",
}
CREDENTIAL_KIND = "production_control_plane_smoke"
MANAGED_BY = "scripts.server.bootstrap_production_control_plane"
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class BootstrapResult:
    tenant_id: str
    key_id: str
    env_file: Path
    api_key_store: Path
    tenant_registry: Path
    pricing_version: str | None = None
    rotated_key_id: str | None = None


def _decode_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        parts = shlex.split(value, comments=False, posix=True)
        if len(parts) != 1:
            raise RuntimeError("invalid quoted environment value")
        return parts[0]
    return value


def read_environment_file(path: str | Path) -> tuple[str, dict[str, str]]:
    env_path = Path(path)
    text = env_path.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise RuntimeError(f"invalid environment assignment at {env_path}:{number}")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not _KEY_RE.fullmatch(key):
            raise RuntimeError(f"invalid environment key at {env_path}:{number}")
        if key in values:
            raise RuntimeError(f"duplicate environment key in {env_path}: {key}")
        values[key] = _decode_env_value(raw_value)
    return text, values


@contextlib.contextmanager
def activated_environment(values: Mapping[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update({key: str(value) for key, value in values.items()})
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def canonicalize_production_runtime_bindings(values: Mapping[str, str]) -> dict[str, str]:
    """Overlay lifecycle-owned immutable production bindings, rejecting drift."""

    result = {str(key): str(value) for key, value in values.items()}
    for key, expected in CANONICAL_RUNTIME_BINDINGS.items():
        actual = str(result.get(key) or "").strip()
        if actual and actual != expected:
            raise RuntimeError(
                f"canonical production binding mismatch: {key}={actual!r}; expected {expected!r}"
            )
        result[key] = expected
    return result


def _require_production(values: Mapping[str, str]) -> None:
    env_name = (values.get("APP_ENV") or values.get("ENV") or "").strip().lower()
    if env_name not in {"prod", "production"}:
        raise RuntimeError("APP_ENV must be prod/production")
    if not str(values.get("API_CONTROL_PLANE_API_KEY_PEPPER") or "").strip():
        raise RuntimeError("API_CONTROL_PLANE_API_KEY_PEPPER is required")
    if str(values.get("BUSINESAIOS_API_KEY_STORE_BACKEND") or "file").strip().lower() != "file":
        raise RuntimeError("production API key store must use file backend")
    if str(values.get("BUSINESAIOS_TENANT_REGISTRY_BACKEND") or "file").strip().lower() != "file":
        raise RuntimeError("production tenant registry must use file backend")


def _validate_env_destination(path: Path) -> None:
    if path == CANONICAL_PRODUCTION_ENV_FILE and (
        os.name != "posix" or getattr(os, "geteuid", lambda: -1)() != 0
    ):
        raise PermissionError(f"root is required to update {CANONICAL_PRODUCTION_ENV_FILE}")
    if not path.exists():
        raise FileNotFoundError(f"production environment file does not exist: {path}")
    if path.is_symlink():
        raise RuntimeError(f"production environment file must not be a symlink: {path}")


def _rewrite_managed_assignments(
    text: str,
    *,
    credential: str,
    tenant_id: str,
    pricing_version: str | None = None,
    runtime_bindings: Mapping[str, str] | None = None,
) -> str:
    replacements = {
        **dict(runtime_bindings or {}),
        "CONTROL_PLANE_API_KEY": credential,
        "SMOKE_TENANT_ID": tenant_id,
    }
    if pricing_version is not None:
        replacements["PRICING_VERSION"] = pricing_version
    seen: set[str] = set()
    output: list[str] = []
    assignment = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
    for line in text.splitlines():
        match = assignment.match(line)
        key = match.group(1) if match else None
        if key in replacements:
            if key in seen:
                raise RuntimeError(f"duplicate managed environment key: {key}")
            output.append(f"{key}={replacements[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in replacements.items():
        if key not in seen:
            output.append(f"{key}={value}")
    return "\n".join(output) + "\n"


def _atomic_write_private(path: Path, text: str) -> None:
    current = path.lstat()
    if stat.S_ISLNK(current.st_mode):
        raise RuntimeError(f"refusing symlink environment file: {path}")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        if hasattr(os, "fchown"):
            os.fchown(fd, current.st_uid, current.st_gid)
        with os.fdopen(fd, "w", encoding="utf-8", closefd=True) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        tmp.unlink(missing_ok=True)
        raise


def _key_id_from_token(token: str) -> str | None:
    value = str(token or "").strip()
    if "." not in value:
        return None
    key_id, raw_secret = value.split(".", 1)
    return key_id if key_id and raw_secret else None


def _is_lifecycle_record(record: ApiKeyRecord | None) -> bool:
    if record is None:
        return False
    return (
        str(record.metadata.get("credential_kind") or "") == CREDENTIAL_KIND
        and str(record.metadata.get("managed_by") or "") == MANAGED_BY
    )


def _load_persistent_surfaces(values: Mapping[str, str]) -> tuple[PersistentApiKeyStore, PersistentTenantRegistry]:
    pepper = str(values.get("API_CONTROL_PLANE_API_KEY_PEPPER") or "").strip()
    with activated_environment(values):
        store = build_default_api_key_store(pepper=pepper)
        registry = build_default_tenant_registry()
    if not isinstance(store, PersistentApiKeyStore):
        raise RuntimeError("canonical production API key store is not persistent")
    if not isinstance(registry, PersistentTenantRegistry):
        raise RuntimeError("canonical production tenant registry is not persistent")
    if not store.path.is_absolute() or not registry.path.is_absolute():
        raise RuntimeError("production security and tenant stores must use absolute paths")
    return store, registry


def validate_credential_binding(
    *,
    credential: str,
    tenant_id: str,
    values: Mapping[str, str],
) -> str:
    _require_production(values)
    store, registry = _load_persistent_surfaces(values)
    tenant = registry.assert_active(tenant_id)
    key_id = _key_id_from_token(credential)
    if not key_id:
        raise RuntimeError("CONTROL_PLANE_API_KEY is malformed")
    record = store.get(key_id)
    if record is None or not record.is_active():
        raise RuntimeError("CONTROL_PLANE_API_KEY is not an active canonical API key")
    if record.tenant_id != tenant.tenant_id:
        raise RuntimeError("CONTROL_PLANE_API_KEY tenant binding mismatch")
    if RoleId.OWNER not in record.roles:
        raise RuntimeError("CONTROL_PLANE_API_KEY lacks OWNER role required by production smoke")
    if "provider_control_plane" not in record.scopes:
        raise RuntimeError("CONTROL_PLANE_API_KEY lacks provider_control_plane scope required by production smoke")
    if not _is_lifecycle_record(record):
        raise RuntimeError("CONTROL_PLANE_API_KEY was not issued by canonical production bootstrap")
    _, raw_secret = credential.split(".", 1)
    if not store.verify_secret(key_id=key_id, raw_secret=raw_secret):
        raise RuntimeError("CONTROL_PLANE_API_KEY secret does not match application-side hash")
    return key_id


def validate_current_binding_from_environment(path: str | Path = DEFAULT_ENV_FILE) -> str:
    _, values = read_environment_file(path)
    credential = str(values.get("CONTROL_PLANE_API_KEY") or "").strip()
    tenant_id = str(values.get("SMOKE_TENANT_ID") or "").strip()
    if not credential:
        raise RuntimeError("CONTROL_PLANE_API_KEY is required")
    if not tenant_id:
        raise RuntimeError("SMOKE_TENANT_ID is required")
    return validate_credential_binding(credential=credential, tenant_id=tenant_id, values=values)


def bootstrap_production_control_plane(
    *,
    tenant_id: str,
    env_file: str | Path = DEFAULT_ENV_FILE,
    pricing_version: str | None = None,
) -> BootstrapResult:
    path = Path(env_file)
    tenant_id = str(tenant_id or "").strip()
    if not tenant_id or tenant_id == "default-business":
        raise RuntimeError("explicit non-default production tenant_id is required")
    approved_pricing_version = (
        validate_explicit_pricing_version(pricing_version)
        if pricing_version is not None
        else None
    )

    # Serialize the complete environment cutover. PersistentApiKeyStore owns a
    # separate store-level lock for every key mutation, so live API writers and
    # this lifecycle reconcile against the same latest on-disk snapshot.
    with exclusive_file_lock(path):
        _validate_env_destination(path)
        original_text, raw_values = read_environment_file(path)
        runtime_bindings: Mapping[str, str] = {}
        if path == CANONICAL_PRODUCTION_ENV_FILE:
            values = canonicalize_production_runtime_bindings(raw_values)
            runtime_bindings = CANONICAL_RUNTIME_BINDINGS
        else:
            values = dict(raw_values)
        _require_production(values)
        store, registry = _load_persistent_surfaces(values)
        tenant = registry.assert_active(tenant_id)
        old_token = str(values.get("CONTROL_PLANE_API_KEY") or "").strip()
        old_key_id = _key_id_from_token(old_token)
        old_record = store.get(old_key_id) if old_key_id else None
        rotated_key_id = old_record.key_id if _is_lifecycle_record(old_record) else None

        # A prior process may have died after switching api.env but before
        # revoking its superseded lifecycle key. Retire every active orphan
        # owned by this lifecycle before issuing another candidate, while
        # preserving the currently env-bound key until the cutover succeeds.
        for candidate in store.list_records():
            if (
                candidate.key_id != rotated_key_id
                and candidate.is_active()
                and _is_lifecycle_record(candidate)
            ):
                store.revoke(candidate.key_id)

        record, credential = store.issue(
            tenant_id=tenant.tenant_id,
            subject=f"production-control-plane-smoke:{tenant.tenant_id}",
            actor_id=f"production-control-plane-smoke:{tenant.tenant_id}",
            roles=(RoleId.OWNER,),
            scopes=("provider_control_plane",),
            display_name=f"Production control-plane smoke ({tenant.tenant_id})",
            metadata={
                "principal_kind": "service",
                "credential_kind": CREDENTIAL_KIND,
                "managed_by": MANAGED_BY,
            },
        )
        try:
            key_id = validate_credential_binding(
                credential=credential,
                tenant_id=tenant.tenant_id,
                values=values,
            )
            store_text = store.path.read_text(encoding="utf-8")
            if credential in store_text:
                raise RuntimeError("plaintext credential leaked into application API key store")
            updated_text = _rewrite_managed_assignments(
                original_text,
                credential=credential,
                tenant_id=tenant.tenant_id,
                pricing_version=approved_pricing_version,
                runtime_bindings=runtime_bindings,
            )
            _atomic_write_private(path, updated_text)
        except BaseException:
            store.revoke(record.key_id)
            raise

        if rotated_key_id and rotated_key_id != record.key_id:
            # revoke() reloads the latest store snapshot under the store lock,
            # preserving keys issued concurrently by the running API process.
            current_store, _ = _load_persistent_surfaces(values)
            current_old = current_store.get(rotated_key_id)
            if current_old is not None and current_old.is_active():
                current_store.revoke(rotated_key_id)

        # Re-read the only persistent plaintext surface and prove it resolves
        # through the same application-side hash/pepper/tenant contracts.
        key_id = validate_current_binding_from_environment(path)
        return BootstrapResult(
            tenant_id=tenant.tenant_id,
            key_id=key_id,
            env_file=path,
            api_key_store=store.path,
            tenant_registry=registry.path,
            pricing_version=approved_pricing_version,
            rotated_key_id=rotated_key_id,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Issue and bind the canonical production control-plane smoke credential."
    )
    parser.add_argument("--tenant-id", required=True, help="Existing active production tenant ID.")
    parser.add_argument(
        "--pricing-version",
        help=(
            "Operator-approved production pricing version to atomically bind in api.env. "
            "The canonical host lifecycle always supplies this value."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = bootstrap_production_control_plane(
        tenant_id=args.tenant_id,
        env_file=DEFAULT_ENV_FILE,
        pricing_version=args.pricing_version,
    )
    rotation = f" rotated_key_id={result.rotated_key_id}" if result.rotated_key_id else ""
    pricing = f" pricing_version={result.pricing_version}" if result.pricing_version else ""
    print(
        "PRODUCTION_CONTROL_PLANE_BOOTSTRAP_OK "
        f"tenant_id={result.tenant_id} key_id={result.key_id}{rotation}{pricing} "
        f"env_file={result.env_file}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
