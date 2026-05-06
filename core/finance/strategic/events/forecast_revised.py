from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastRevised:
    forecast_version: str
    summary: str
