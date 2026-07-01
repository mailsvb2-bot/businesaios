from __future__ import annotations

from pathlib import Path

from contracts.product_contract import EconomicsConfigV1, OfferCatalog, ProductContract
from core.economics.economics_config import EconomicsConfigV1 as CoreEconomicsConfigV1
from core.payments.contracts import validate_payment_external_id

ROOT = Path(__file__).resolve().parents[2]


FORBIDDEN_SECOND_PAYMENT_BRAIN_FILENAMES = {
    "payment_canon.py",
    "provider_canon.py",
    "provider_registry.py",
    "payment_provider_registry.py",
}

PAYMENT_BOUNDARY = ROOT / "core" / "payments"
PRODUCT_CONTRACT = ROOT / "contracts" / "product_contract.py"
ECONOMICS_CONTRACT = ROOT / "contracts" / "economics_config.py"
CORE_ECONOMICS_CONFIG = ROOT / "core" / "economics" / "economics_config.py"


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_existing_product_contract_remains_economics_and_offer_boundary() -> None:
    contract = ProductContract(tenant_id="tenant", product_id="product", domain="metrotherapy")

    assert isinstance(contract.offer_catalog, OfferCatalog)
    assert isinstance(contract.economics, EconomicsConfigV1)
    assert EconomicsConfigV1 is CoreEconomicsConfigV1
    assert hasattr(contract, "entitlements")


def test_existing_payment_contract_remains_payment_id_boundary() -> None:
    assert validate_payment_external_id("pay_123456") == "pay_123456"


def test_payment_boundary_does_not_grow_second_contract_brain() -> None:
    offenders = [
        _relative(path)
        for path in PAYMENT_BOUNDARY.rglob("*.py")
        if path.name in FORBIDDEN_SECOND_PAYMENT_BRAIN_FILENAMES
    ]

    assert offenders == []


def test_provider_sdk_imports_do_not_enter_canonical_business_layers() -> None:
    scanned_roots = (
        ROOT / "core",
        ROOT / "contracts",
        ROOT / "runtime",
        ROOT / "interfaces",
    )
    provider_import_markers = (
        "import airwallex",
        "from airwallex",
        "import yookassa",
        "from yookassa",
        "import stripe",
        "from stripe",
        "import paddle",
        "from paddle",
        "import mollie",
        "from mollie",
    )

    offenders: list[str] = []
    for scanned_root in scanned_roots:
        if not scanned_root.exists():
            continue
        for path in scanned_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for marker in provider_import_markers:
                if marker in text:
                    offenders.append(f"{_relative(path)}:{marker}")

    assert offenders == []


def test_payment_and_economics_boundaries_are_documented_in_existing_files() -> None:
    product_contract_text = PRODUCT_CONTRACT.read_text(encoding="utf-8")
    economics_contract_text = ECONOMICS_CONTRACT.read_text(encoding="utf-8")
    core_economics_text = CORE_ECONOMICS_CONFIG.read_text(encoding="utf-8")

    assert "Single Source of Truth" in product_contract_text
    assert "EconomicsConfigV1" in economics_contract_text
    assert "DecisionCore is the single point" in core_economics_text
