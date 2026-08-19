from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from governance.persistence_codec import atomic_write_json, from_dataclass
from tenancy.tenant_contract import TenantRecord
from tenancy.tenant_policy_store import TenantPolicyBundle

CANON_LEGACY_TENANCY_MIGRATION = True
DEFAULT_LEGACY_DIR = Path("/opt/businesaios/data/tenancy")
DEFAULT_RUNTIME_DIR = Path("/var/lib/businesaios/runtime/tenancy")


@dataclass(frozen=True)
class SurfaceSpec:
    filename: str
    collection_key: str
    model: type[Any]


@dataclass(frozen=True)
class SurfacePlan:
    spec: SurfaceSpec
    target: Path
    payload: dict[str, Any]
    added: tuple[str, ...]
    changed: bool


@dataclass(frozen=True)
class MigrationResult:
    registry_added: tuple[str, ...]
    policies_added: tuple[str, ...]
    runtime_dir: Path


_SURFACES = (
    SurfaceSpec("tenant_registry.json", "records", TenantRecord),
    SurfaceSpec("tenant_policies.json", "bundles", TenantPolicyBundle),
)


def _read_payload(
    path: Path,
    spec: SurfaceSpec,
    *,
    missing_ok: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not path.exists():
        if missing_ok:
            return {spec.collection_key: []}, [], {}
        raise FileNotFoundError(f"required tenancy source is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid tenancy JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"tenancy surface must be a JSON object: {path}")
    raw_items = payload.get(spec.collection_key)
    if not isinstance(raw_items, list):
        raise RuntimeError(
            f"tenancy surface {path} must contain list key {spec.collection_key!r}"
        )

    items: list[dict[str, Any]] = []
    by_tenant: dict[str, dict[str, Any]] = {}
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise RuntimeError(f"invalid tenancy item at {path}:{index}")
        item = dict(raw_item)
        tenant_id = str(item.get("tenant_id") or "").strip()
        if not tenant_id:
            raise RuntimeError(f"missing tenant_id at {path}:{index}")
        if tenant_id in by_tenant:
            raise RuntimeError(f"duplicate tenant_id {tenant_id!r} in {path}")
        try:
            model = from_dataclass(spec.model, item)
            model.validate()
        except Exception as exc:
            raise RuntimeError(
                f"invalid {spec.collection_key} record for tenant {tenant_id!r} in {path}"
            ) from exc
        items.append(item)
        by_tenant[tenant_id] = item
    return payload, items, by_tenant


def _plan_surface(*, legacy_dir: Path, runtime_dir: Path, spec: SurfaceSpec) -> SurfacePlan:
    legacy_path = legacy_dir / spec.filename
    runtime_path = runtime_dir / spec.filename
    if not legacy_path.exists():
        runtime_payload, _, _ = _read_payload(runtime_path, spec, missing_ok=True)
        return SurfacePlan(
            spec=spec,
            target=runtime_path,
            payload=runtime_payload,
            added=(),
            changed=False,
        )

    legacy_payload, legacy_items, _ = _read_payload(legacy_path, spec, missing_ok=False)
    runtime_payload, runtime_items, runtime_by_tenant = _read_payload(
        runtime_path,
        spec,
        missing_ok=True,
    )

    # Canonical runtime state is authoritative for tenant IDs it already owns.
    # Legacy state is only a source for tenant IDs that have not yet crossed the
    # historical checkout -> StateDirectory boundary. Existing runtime records
    # are never replaced from the preserved rollback source.
    added = tuple(
        str(item["tenant_id"])
        for item in legacy_items
        if str(item["tenant_id"]) not in runtime_by_tenant
    )
    merged_items = list(runtime_items)
    merged_items.extend(
        dict(item)
        for item in legacy_items
        if str(item["tenant_id"]) not in runtime_by_tenant
    )

    merged_payload = dict(runtime_payload)
    for key, value in legacy_payload.items():
        if key == spec.collection_key:
            continue
        if key in merged_payload and merged_payload[key] != value:
            raise RuntimeError(
                f"conflicting top-level tenancy metadata {key!r} between {legacy_path} and {runtime_path}"
            )
        merged_payload.setdefault(key, value)
    merged_payload[spec.collection_key] = merged_items

    return SurfacePlan(
        spec=spec,
        target=runtime_path,
        payload=merged_payload,
        added=added,
        changed=merged_payload != runtime_payload,
    )


def _verify_written_plan(plan: SurfacePlan) -> None:
    _, written_items, written_by_tenant = _read_payload(
        plan.target,
        plan.spec,
        missing_ok=False,
    )
    expected_items = plan.payload[plan.spec.collection_key]
    if len(written_items) != len(expected_items):
        raise RuntimeError(f"tenancy migration verification failed for {plan.target}")
    for tenant_id in plan.added:
        if tenant_id not in written_by_tenant:
            raise RuntimeError(
                f"tenancy migration verification lost tenant {tenant_id!r} in {plan.target}"
            )


def migrate_legacy_tenancy_state(
    *,
    legacy_dir: str | Path = DEFAULT_LEGACY_DIR,
    runtime_dir: str | Path = DEFAULT_RUNTIME_DIR,
    write: bool = True,
) -> MigrationResult:
    legacy = Path(legacy_dir)
    runtime = Path(runtime_dir)

    # Build and validate every merge plan before mutating either surface. This
    # prevents a malformed policy file from leaving the registry half-migrated
    # (or vice versa). Cross-file writes cannot be a database transaction, but
    # every deterministic validation failure is resolved before the first write.
    plans = tuple(
        _plan_surface(legacy_dir=legacy, runtime_dir=runtime, spec=spec)
        for spec in _SURFACES
    )

    if write:
        runtime.mkdir(parents=True, exist_ok=True)
        for plan in plans:
            if plan.changed:
                atomic_write_json(plan.target, plan.payload)
        for plan in plans:
            if plan.changed:
                _verify_written_plan(plan)

    added_by_surface = {plan.spec.filename: plan.added for plan in plans}
    return MigrationResult(
        registry_added=added_by_surface["tenant_registry.json"],
        policies_added=added_by_surface["tenant_policies.json"],
        runtime_dir=runtime,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Merge only missing legacy tenant registry/policy records into the canonical runtime StateDirectory."
        )
    )
    parser.add_argument("--legacy-dir", type=Path, default=DEFAULT_LEGACY_DIR)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate and report the merge plan without writing runtime state.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = migrate_legacy_tenancy_state(
        legacy_dir=args.legacy_dir,
        runtime_dir=args.runtime_dir,
        write=not args.check,
    )
    mode = "CHECK_OK" if args.check else "OK"
    registry = ",".join(result.registry_added) or "none"
    policies = ",".join(result.policies_added) or "none"
    print(
        f"TENANCY_MIGRATION_{mode} registry_added={registry} "
        f"policies_added={policies} runtime_dir={result.runtime_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
