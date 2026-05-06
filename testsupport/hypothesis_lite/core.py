from __future__ import annotations

import functools
import inspect
import itertools
import os
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class _Settings:
    max_examples: int = 100
    deadline: Any = None
    suppress_health_check: list[Any] | None = None


class HealthCheck:
    too_slow = "too_slow"


def settings(*, max_examples: int = 100, deadline: Any = None, suppress_health_check: list[Any] | None = None):
    cfg = _Settings(max_examples=max_examples, deadline=deadline, suppress_health_check=suppress_health_check)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        setattr(fn, "_hypothesis_lite_settings", cfg)
        return fn

    return decorator


def _resolve_examples(fn: Callable[..., Any]) -> int:
    cfg = getattr(fn, "_hypothesis_lite_settings", None)
    if cfg is None:
        return int(os.getenv("HYPOTHESIS_MAX_EXAMPLES", "100"))
    return int(cfg.max_examples)


def given(*strategies: Any, **kw_strategies: Any):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            examples = max(1, _resolve_examples(wrapper))
            pos_iters = [iter(s.example_stream()) for s in strategies]
            kw_iters = {name: iter(strategy.example_stream()) for name, strategy in kw_strategies.items()}
            result = None
            for _ in range(examples):
                generated_args = [next(it) for it in pos_iters]
                generated_kwargs = {name: next(it) for name, it in kw_iters.items()}
                bound = signature.bind_partial(*args, *generated_args, **kwargs, **generated_kwargs)
                result = fn(*bound.args, **bound.kwargs)
            return result

        cfg = getattr(fn, "_hypothesis_lite_settings", None)
        if cfg is not None:
            setattr(wrapper, "_hypothesis_lite_settings", cfg)
        wrapper.__signature__ = inspect.Signature()
        return wrapper

    return decorator
