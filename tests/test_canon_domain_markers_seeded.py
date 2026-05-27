from __future__ import annotations

from core.experiments.__canon_domain__ import CANON_DOMAIN_VERSION as EXPERIMENTS_VERSION
from core.finance.__canon_domain__ import CANON_DOMAIN_VERSION as FINANCE_VERSION
from core.human_governance.__canon_domain__ import CANON_DOMAIN_VERSION as HG_VERSION
from core.knowledge.__canon_domain__ import CANON_DOMAIN_VERSION as KNOW_VERSION
from core.learning_loop.__canon_domain__ import CANON_DOMAIN_VERSION as LL_VERSION
from core.product.__canon_domain__ import CANON_DOMAIN_VERSION as PRODUCT_VERSION
from core.simulation.__canon_domain__ import CANON_DOMAIN_VERSION as SIM_VERSION
from core.world_model.__canon_domain__ import CANON_DOMAIN_VERSION as WM_VERSION


def test_seeded_canon_domains_are_marked() -> None:
    assert WM_VERSION == "DFS-V1"
    assert KNOW_VERSION == "DFS-V1"
    assert LL_VERSION == "DFS-V1"
    assert SIM_VERSION == "DFS-V1"
    assert PRODUCT_VERSION == "DFS-V1"
    assert FINANCE_VERSION == "DFS-V1"
    assert EXPERIMENTS_VERSION == "DFS-V1"
    assert HG_VERSION == "DFS-V1"
