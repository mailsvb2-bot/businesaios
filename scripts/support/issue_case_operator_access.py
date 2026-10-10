"""Provision/revoke a bounded support-console key on an ADMINISTRATOR'S server.

This is an interactive administrative tool, not a public API or a parallel
credential database. It uses the existing persistent API key owner.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from entrypoints.api.api_key_policy import PersistentApiKeyStore
from governance.rbac_contract import RoleId

_ID = re.compile(r"^[A-Za-z0-9@._:-]{1,128}$")


def _checked_identity(raw: str, name: str) -> str:
    value = str(raw or "").strip()
    if not _ID.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def issue_operator_access(
    *, store: PersistentApiKeyStore, tenant_id: str, business_id: str,
    operator_id: str, ttl_seconds: int = 3600,
) -> tuple[str, str]:
    """Issue an expiring, tenant+business-bound canonical SUPPORT credential."""
    tenant_id = _checked_identity(tenant_id, "tenant_id")
    business_id = _checked_identity(business_id, "business_id")
    operator_id = _checked_identity(operator_id, "operator_id")
    if type(ttl_seconds) is not int or not 300 <= ttl_seconds <= 28800:
        raise ValueError("support operator TTL must be 300..28800 seconds")
    record, secret = store.issue(
        tenant_id=tenant_id, subject=operator_id, actor_id=operator_id,
        roles=(RoleId.SUPPORT,), scopes=("support_case_manage",),
        ttl_seconds=ttl_seconds,
        metadata={
            "business_id": business_id,
            "principal_kind": "user",
            "session_kind": "support_case_operator",
        },
    )
    return record.key_id, secret


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue/revoke one business-scoped support console key")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    issue = subparsers.add_parser("issue")
    issue.add_argument("--tenant", required=True)
    issue.add_argument("--business", required=True)
    issue.add_argument("--operator", required=True)
    issue.add_argument("--ttl-seconds", type=int, default=3600)
    revoke = subparsers.add_parser("revoke")
    revoke.add_argument("--key-id", required=True)
    args = parser.parse_args()

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("interactive administrator terminal required; never emit keys to CI logs")
    if os.getenv("BUSINESAIOS_API_KEY_STORE_BACKEND", "file").strip().lower() != "file":
        parser.error("persistent canonical API key store required")
    path = os.getenv("BUSINESAIOS_API_KEY_STORE_PATH", "").strip()
    pepper = os.getenv("API_CONTROL_PLANE_API_KEY_PEPPER", "").strip()
    if not path or not pepper:
        parser.error("BUSINESAIOS_API_KEY_STORE_PATH and API_CONTROL_PLANE_API_KEY_PEPPER are required")
    if input("Type SUPPORT ACCESS to change live credentials: ").strip() != "SUPPORT ACCESS":
        parser.error("operator credential change not confirmed")
    store = PersistentApiKeyStore(path=path, pepper=pepper)

    if args.operation == "revoke":
        key_id = _checked_identity(args.key_id, "key_id")
        record = store.get(key_id)
        if record is None or RoleId.SUPPORT not in record.roles or "support_case_manage" not in record.scopes:
            parser.error("key is not a support-console credential")
        store.revoke(key_id)
        print("Revoked support credential:", key_id)
        return

    key_id, secret = issue_operator_access(
        store=store, tenant_id=args.tenant, business_id=args.business,
        operator_id=args.operator, ttl_seconds=args.ttl_seconds,
    )
    print("Key ID:", key_id)
    print("Temporary key (shown once; do not store in logs or messages):")
    print(secret)
    print("Use at ?support_console=1; revoke by key ID or let it expire.")


if __name__ == "__main__":
    main()
