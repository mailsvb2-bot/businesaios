from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from config.yaml_loader_shared import load_yaml
from config.env_flags import env_str

from contracts.autopilot_contract import (
    AutopilotConstraints,
    AutopilotContract,
    ControlSurface,
    DataRequirements,
    SafetyPolicy,
)


def _as_dict(x: Any) -> dict:
    return dict(x) if isinstance(x, Mapping) else {}


@dataclass(frozen=True)
class AutopilotContractLoader:
    base_dir: Path

    def load(self, ref: str, *, tenant_id: str) -> AutopilotContract:
        """Load an autopilot contract by ref.

        Rules:
        - ref is a filename relative to base_dir.
        - ref must stay within base_dir.
        """

        r = str(ref or "").strip() or "default.yaml"
        if not r.endswith(".yaml"):
            r = f"{r}.yaml"

        base = self.base_dir.resolve()
        path = (base / r).resolve()
        if base not in path.parents and path != base:
            raise ValueError(f"AUTOPILOT_CONTRACT_REF must be within config/autopilot/: {ref}")
        raw = load_yaml(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("BAD_AUTOPILOT_CONTRACT")

        contract_id = str(raw.get("contract_id") or "").strip() or "autopilot_default@v1"
        ns = str(raw.get("north_star_metric") or "profit").strip() or "profit"

        c_raw = _as_dict(raw.get("constraints"))
        d_raw = _as_dict(raw.get("data_requirements"))
        s_raw = _as_dict(raw.get("safety_policy"))
        cs_raw = _as_dict(raw.get("control_surface"))

        ctr = AutopilotContract(
            contract_id=contract_id,
            tenant_id=str(tenant_id or "").strip(),
            north_star_metric=ns,
            constraints=AutopilotConstraints(
                max_price_changes_per_day=int(c_raw.get("max_price_changes_per_day", 1) or 1),
                cooldown_hours=int(c_raw.get("cooldown_hours", 24) or 24),
                daily_budget_minor=int(c_raw.get("daily_budget_minor", 0) or 0),
                currency=str(c_raw.get("currency", "RUB") or "RUB"),
            ),
            data_requirements=DataRequirements(
                required_event_types=tuple(str(x) for x in (d_raw.get("required_event_types") or []) if str(x).strip())
                or DataRequirements().required_event_types,
                optional_event_types=tuple(str(x) for x in (d_raw.get("optional_event_types") or []) if str(x).strip()),
            ),
            control_surface=ControlSurface(
                can_change_offer=bool(cs_raw.get("can_change_offer", True)),
                can_change_price=bool(cs_raw.get("can_change_price", True)),
                can_change_copy=bool(cs_raw.get("can_change_copy", True)),
                can_change_frequency=bool(cs_raw.get("can_change_frequency", True)),
            ),
            safety_policy=SafetyPolicy(
                stop_loss_max_cac_minor=int(s_raw.get("stop_loss_max_cac_minor", 0) or 0),
                stop_loss_min_profit_minor=int(s_raw.get("stop_loss_min_profit_minor", 0) or 0),
                stop_loss_cac_days=int(s_raw.get("stop_loss_cac_days", 1) or 1),
                stop_loss_profit_days=int(s_raw.get("stop_loss_profit_days", 1) or 1),
                stop_loss_max_spend_minor_no_conv=int(s_raw.get("stop_loss_max_spend_minor_no_conv", 0) or 0),
                stop_loss_no_conv_days=int(s_raw.get("stop_loss_no_conv_days", 1) or 1),
                allow_channels=tuple(str(x) for x in (s_raw.get("allow_channels") or ["internal"]) if str(x).strip())
                or ("internal",),
            ),
            metadata=_as_dict(raw.get("metadata")),
        )
        ctr.validate()
        return ctr


def load_autopilot_contract_from_env(*, tenant_id: str, ref: str = "") -> AutopilotContract:
    """Load autopilot contract.

    Env:
      AUTOPILOT_CONTRACT_REF=default (default)
    """
    base = Path(__file__).resolve().parents[2] / "config" / "autopilot"
    loader = AutopilotContractLoader(base_dir=base)
    r = str(ref or env_str("AUTOPILOT_CONTRACT_REF", "") or "").strip()
    return loader.load(r or "default", tenant_id=str(tenant_id or "").strip())
