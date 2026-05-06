from __future__ import annotations

from pathlib import Path

from runtime.tenancy import require_tenant_id


def resolve_catalog_path(*, tenant_id: str, product: str, env: str) -> tuple[Path, Path]:
    tenant = require_tenant_id(tenant_id)
    prod = str(product).strip() or "organization_platform"
    envv = str(env).strip() or "prod"
    repo_root = Path(__file__).resolve().parents[3]
    base = (repo_root / "data" / "offer_catalogs").resolve()
    cat_path = (base / tenant / prod / f"{envv}.yaml").resolve()
    if not str(cat_path).startswith(str(base)):
        raise RuntimeError("BAD_CATALOG_PATH")
    return base, cat_path


def append_line(text: str, line: str) -> str:
    text = (text or "").rstrip()
    if not text:
        return str(line)
    return text + "\n" + str(line)
