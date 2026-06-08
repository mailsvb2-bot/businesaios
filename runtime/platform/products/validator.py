from __future__ import annotations

from dataclasses import dataclass

from contracts.product_contract import ProductContract


@dataclass(frozen=True)
class ContractValidationIssue:
    code: str
    message: str


class ProductContractValidator:
    """Returns structured issues (for CI / boot self-check), not just exceptions."""

    def validate(self, contract: ProductContract) -> tuple[ContractValidationIssue, ...]:
        issues: list[ContractValidationIssue] = []
        try:
            contract.validate()
        except Exception as e:
            issues.append(ContractValidationIssue(code="contract_invalid", message=str(e)))
            return tuple(issues)

        # Telemetry must include minimal commerce + UX events
        required = {"ui_click", "offer_shown", "offer_clicked", "purchase_attempt", "purchase_success", "purchase_failed"}
        present = {ev.event_type for ev in contract.telemetry_schema.events}
        missing = required - present
        if missing:
            issues.append(
                ContractValidationIssue(
                    code="telemetry_minimum_missing",
                    message=f"Missing telemetry event_types: {sorted(missing)}",
                )
            )

        # Pricing model should resolve to known offer IDs (defensive check with empty context)
        try:
            chosen = contract.pricing_model.choose_offer_id(user_id="__probe__", tenant_id="__probe__", context={})
            known = {o.offer_id for o in contract.offer_catalog.offers}
            if chosen not in known:
                issues.append(
                    ContractValidationIssue(
                        code="pricing_model_offer_unknown",
                        message=f"PricingModel.choose_offer_id returned '{chosen}' which is not in offer_catalog",
                    )
                )
        except Exception as e:
            issues.append(ContractValidationIssue(code="pricing_model_error", message=str(e)))

        return tuple(issues)
