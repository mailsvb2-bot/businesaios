from __future__ import annotations

import itertools
import math
from dataclasses import is_dataclass
from typing import Any, Callable


class Strategy:
    def __init__(self, generator: Callable[[], Any]) -> None:
        self._generator = generator

    def example_stream(self):
        while True:
            yield self._generator()


def _cycle(values: list[Any]) -> Callable[[], Any]:
    it = itertools.cycle(values)
    return lambda: next(it)


def booleans() -> Strategy:
    return Strategy(_cycle([False, True]))


def floats(
    *,
    min_value: float | None = None,
    max_value: float | None = None,
    allow_nan: bool = False,
    allow_infinity: bool = False,
    width: int | None = None,
) -> Strategy:
    candidates = [
        -1_000_000.0,
        -1.0,
        -1e-12,
        0.0,
        1e-12,
        0.1,
        0.15,
        0.2,
        0.25,
        0.4,
        0.9,
        1.0,
        5.0,
        1_000_000.0,
    ]
    if allow_nan:
        candidates.append(math.nan)
    if allow_infinity:
        candidates.extend([math.inf, -math.inf])

    filtered = []
    for value in candidates:
        if math.isnan(value) and not allow_nan:
            continue
        if math.isinf(value) and not allow_infinity:
            continue
        if min_value is not None and not math.isnan(value) and value < min_value:
            continue
        if max_value is not None and not math.isnan(value) and value > max_value:
            continue
        filtered.append(value)
    if not filtered:
        fallback = 0.0
        if min_value is not None:
            fallback = max(fallback, min_value)
        if max_value is not None:
            fallback = min(fallback, max_value)
        filtered = [fallback]
    return Strategy(_cycle(filtered))


def builds(factory: Callable[..., Any], /, *args: Strategy, **kwargs: Strategy) -> Strategy:
    arg_iters = [iter(arg.example_stream()) for arg in args]
    kw_iters = {name: iter(strategy.example_stream()) for name, strategy in kwargs.items()}

    def generate() -> Any:
        built_args = [next(it) for it in arg_iters]
        built_kwargs = {name: next(it) for name, it in kw_iters.items()}
        return factory(*built_args, **built_kwargs)

    return Strategy(generate)
