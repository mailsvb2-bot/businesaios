from __future__ import annotations

from pathlib import Path


TEST_FILES = (
    "tests/unit/client_outcome/test_client_outcome_commercial_state_routes.py",
    "tests/unit/client_outcome/test_client_outcome_corrected_economics_and_idempotency.py",
    "tests/unit/client_outcome/test_client_outcome_dispute_admin_routes.py",
    "tests/unit/client_outcome/test_client_outcome_full_cycle_routes.py",
    "tests/unit/client_outcome/test_client_outcome_lifecycle_routes.py",
    "tests/unit/client_outcome/test_client_outcome_order_amendment_and_reconciliation.py",
)


def replace_once(text: str, old: str, new: str, *, path: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old!r}")
    return text.replace(old, new, 1)


helper_path = Path("tests/unit/client_outcome/auth_test_support.py")
if helper_path.exists():
    raise RuntimeError(f"unexpected existing helper: {helper_path}")
helper_path.write_text(
    "from __future__ import annotations\n\n"
    "from entrypoints.api.auth_contract import AuthPrincipal\n"
    "from governance.rbac_contract import RoleId\n\n\n"
    "class AuthenticatedTestBundle:\n"
    "    \"\"\"Minimal authenticated perimeter for client-outcome route unit tests.\"\"\"\n\n"
    "    def authenticate(self, *, request, request_context, authorization, x_api_key) -> AuthPrincipal:\n"
    "        tenant_id = request_context.tenant_id or request.headers.get('x-tenant-id') or 'tenant-1'\n"
    "        return AuthPrincipal(\n"
    "            subject='client-outcome-route-test',\n"
    "            tenant_id=tenant_id,\n"
    "            actor_id='client-outcome-route-test',\n"
    "            roles=(RoleId.SYSTEM,),\n"
    "            metadata={'auth_type': 'api_key'},\n"
    "        )\n",
    encoding="utf-8",
)

for raw_path in TEST_FILES:
    path = Path(raw_path)
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from entrypoints.api.request_context import RequestContext\n",
        "from entrypoints.api.request_context import RequestContext\n"
        "from tests.unit.client_outcome.auth_test_support import AuthenticatedTestBundle\n",
        path=raw_path,
    )
    text = replace_once(
        text,
        "        security_guard=_PermissiveGuard(),\n        analytics_handlers=None,\n",
        "        security_guard=_PermissiveGuard(),\n"
        "        auth_bundle=AuthenticatedTestBundle(),\n"
        "        analytics_handlers=None,\n",
        path=raw_path,
    )
    path.write_text(text, encoding="utf-8")
