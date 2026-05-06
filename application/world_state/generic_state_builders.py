from __future__ import annotations

from typing import Mapping


def build_architecture_state(values: Mapping[str, float]) -> dict[str, float]:
    return {str(k): float(v) for k, v in values.items()}


def build_structure_state(values: Mapping[str, float]) -> dict[str, float]:
    return {str(k): float(v) for k, v in values.items()}


def build_flow_state(values: Mapping[str, float]) -> dict[str, float]:
    return {str(k): float(v) for k, v in values.items()}


def build_diffusion_state(values: Mapping[str, float]) -> dict[str, float]:
    return {str(k): float(v) for k, v in values.items()}
