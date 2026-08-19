import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace

from governance.persistence_codec import atomic_write_json, from_dataclass
from tenancy.tenant_contract import TenantRecord
from tenancy.tenant_policy_store import TenantPolicyBundle

DEFAULT_LEGACY_DIR, DEFAULT_RUNTIME_DIR = Path("/opt/businesaios/data/tenancy"), Path("/var/lib/businesaios/runtime/tenancy")
_SURFACES = (("tenant_registry.json", "records", TenantRecord), ("tenant_policies.json", "bundles", TenantPolicyBundle))


def _load(path: Path, key: str, model: type, *, missing_ok: bool) -> tuple[dict, list[dict]]:
    if not path.exists():
        if missing_ok:
            return {key: []}, []
        raise FileNotFoundError(f"required tenancy source is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid tenancy JSON: {path}") from exc
    items = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise RuntimeError(f"tenancy surface {path} must contain list key {key!r}")
    seen: set[str] = set()
    normalized: list[dict] = []
    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise RuntimeError(f"invalid tenancy item at {path}:{index}")
        item = dict(raw)
        tenant_id = str(item.get("tenant_id") or "").strip()
        if not tenant_id:
            raise RuntimeError(f"missing tenant_id at {path}:{index}")
        if tenant_id in seen:
            raise RuntimeError(f"duplicate tenant_id {tenant_id!r} in {path}")
        try:
            from_dataclass(model, item).validate()
        except Exception as exc:
            raise RuntimeError(f"invalid {key} record for tenant {tenant_id!r} in {path}") from exc
        seen.add(tenant_id)
        normalized.append(item)
    return payload, normalized


def _plan(legacy: Path, runtime: Path, filename: str, key: str, model: type) -> tuple:
    source, target = legacy / filename, runtime / filename
    current, current_items = _load(target, key, model, missing_ok=True)
    if not source.exists():
        return target, key, model, current, (), False
    old, old_items = _load(source, key, model, missing_ok=False)
    owned = {str(item["tenant_id"]) for item in current_items}
    additions = [item for item in old_items if str(item["tenant_id"]) not in owned]
    merged = dict(current)
    for name, value in old.items():
        if name == key:
            continue
        if name in merged and merged[name] != value:
            raise RuntimeError(f"conflicting top-level tenancy metadata {name!r} between {source} and {target}")
        merged.setdefault(name, value)
    merged[key] = current_items + additions
    return target, key, model, merged, tuple(str(item["tenant_id"]) for item in additions), merged != current


def migrate_legacy_tenancy_state(
    *, legacy_dir: str | Path = DEFAULT_LEGACY_DIR, runtime_dir: str | Path = DEFAULT_RUNTIME_DIR, write: bool = True
) -> SimpleNamespace:
    legacy, runtime = Path(legacy_dir), Path(runtime_dir)
    plans = [_plan(legacy, runtime, *spec) for spec in _SURFACES]
    if write:
        if os.name == "posix":
            anchor = runtime if runtime.exists() else runtime.parent
            if os.geteuid() != anchor.stat().st_uid:
                raise PermissionError(f"tenancy migration write must run as the runtime directory owner: {anchor}")
        runtime.mkdir(parents=True, exist_ok=True)
        for target, key, model, payload, added, changed in plans:
            if not changed:
                continue
            atomic_write_json(target, payload)
            target.chmod(0o640)
            _, written = _load(target, key, model, missing_ok=False)
            if not set(added).issubset({str(item["tenant_id"]) for item in written}):
                raise RuntimeError(f"tenancy migration verification failed for {target}")
    added = {target.name: ids for target, _, _, _, ids, _ in plans}
    return SimpleNamespace(
        registry_added=added["tenant_registry.json"], policies_added=added["tenant_policies.json"], runtime_dir=runtime
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-dir", type=Path, default=DEFAULT_LEGACY_DIR)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    result = migrate_legacy_tenancy_state(legacy_dir=args.legacy_dir, runtime_dir=args.runtime_dir, write=not args.check)
    mode = "CHECK_OK" if args.check else "OK"
    print(
        f"TENANCY_MIGRATION_{mode} registry_added={','.join(result.registry_added) or 'none'} "
        f"policies_added={','.join(result.policies_added) or 'none'} runtime_dir={result.runtime_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
