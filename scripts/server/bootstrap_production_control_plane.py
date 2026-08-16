from __future__ import annotations

import argparse
import contextlib
import os
import re
import shlex
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping

from entrypoints.api.api_key_policy import PersistentApiKeyStore, build_default_api_key_store
from governance.persistence_codec import exclusive_file_lock
from governance.rbac_contract import RoleId
from tenancy.tenant_registry import PersistentTenantRegistry, build_default_tenant_registry

CANON_PRODUCTION_CONTROL_PLANE_BOOTSTRAP = True

DEFAULT_ENV_FILE = Path("/etc/businesaios/api.env")
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
    if path == DEFAULT_ENV_FILE:
        if os.name != "posix" or getattr(os, "geteuid", lambda: -1)() != 0:
            raise PermissionError(f"root is required to update {DEFAULT_ENV_FILE}")
    if not path.exists():
        raise FileNotFoundError(f"production environment file does not exist: {path}")
    if path.is_symlink():
        raise RuntimeError(f"production environment file must not be a symlink: {path}")


def _rewrite_managed_assignments(text: str, *, credential: str, tenant_id: str) -> str:
    replacements = {
        "CONTROL_PLANE_API_KEY": credential,
        "SMOKE_TENANT_ID": tenant_id,
    }
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
    current = path.stat()
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
        try:
            os.close(fd)
        except OSError:
            pass
        tmp.unlink(missing_ok=True)
        raise


def _key_id_from_token(token: str) -> str | None:
    value = str(token or "").strip()
    if "." not in value:
        return None
    key_id, raw_secret = value.split(".", 1)
    return key_id if key_id and raw_secret else None


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
    if str(record.metadata.get("credential_kind") or "") != CREDENTIAL_KIND:
        raise RuntimeError("CONTROL_PLANE_API_KEY was not issued by canonical production bootstrap")
    if str(record.metadata.get("managed_by") or "") != MANAGED_BY:
        raise RuntimeError("CONTROL_PLANE_API_KEY lifecycle owner mismatch")
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
) -> BootstrapResult:
    path = Path(env_file)
    _validate_env_destination(path)
    original_text, values = read_environment_file(path)
    _require_production(values)
    tenant_id = str(tenant_id or "").strip()
    if not tenant_id or tenant_id == "default-business":
        raise RuntimeError("explicit non-default production tenant_id is required")

    store, registry = _load_persistent_surfaces(values)
    tenant = registry.assert_active(tenant_id)
    old_token = str(values.get("CONTROL_PLANE_API_KEY") or "").strip()
    old_key_id = _key_id_from_token(old_token)
    rotated_key_id: str | None = None

    lock_path = store.path
    with exclusive_file_lock(lock_path):
        # Reload under the lifecycle lock so two bootstrap invocations cannot
        # derive state from the same stale file snapshot.
        with activated_environment(values):
            locked_store = build_default_api_key_store(
                pepper=str(values["API_CONTROL_PLANE_API_KEY_PEPPER"]).strip()
            )
        if not isinstance(locked_store, PersistentApiKeyStore):
            raise RuntimeError("canonical production API key store is not persistent")
        old_record = locked_store.get(old_key_id) if old_key_id else None
        if (
            old_record is not None
            and old_record.tenant_id == tenant.tenant_id
            and str(old_record.metadata.get("credential_kind") or "") == CREDENTIAL_KIND
            and str(old_record.metadata.get("managed_by") or "") == MANAGED_BY
        ):
            rotated_key_id = old_record.key_id

        record, credential = locked_store.issue(
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
            store_text = locked_store.path.read_text(encoding="utf-8")
            if credential in store_text:
                raise RuntimeError("plaintext credential leaked into application API key store")
            updated_text = _rewrite_managed_assignments(
                original_text,
                credential=credential,
                tenant_id=tenant.tenant_id,
            )
            _atomic_write_private(path, updated_text)
        except BaseException:
            locked_store.revoke(record.key_id)
            raise

        if rotated_key_id and rotated_key_id != record.key_id:
            current_old = locked_store.get(rotated_key_id)
            if current_old is not None and current_old.is_active():
                locked_store.revoke(rotated_key_id)

    # Re-read the only persistent plaintext surface and prove it resolves
    # through the same application-side hash/pepper/tenant contracts.
    key_id = validate_current_binding_from_environment(path)
    return BootstrapResult(
        tenant_id=tenant.tenant_id,
        key_id=key_id,
        env_file=path,
        api_key_store=locked_store.path,
        tenant_registry=registry.path,
        rotated_key_id=rotated_key_id,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Issue and bind the canonical production control-plane smoke credential."
    )
    parser.add_argument("--tenant-id", required=True, help="Existing active production tenant ID.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = bootstrap_production_control_plane(
        tenant_id=args.tenant_id,
        env_file=args.env_file,
    )
    rotation = f" rotated_key_id={result.rotated_key_id}" if result.rotated_key_id else ""
    print(
        "PRODUCTION_CONTROL_PLANE_BOOTSTRAP_OK "
        f"tenant_id={result.tenant_id} key_id={result.key_id}{rotation} "
        f"env_file={result.env_file}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
