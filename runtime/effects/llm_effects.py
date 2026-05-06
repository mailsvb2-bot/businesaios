from __future__ import annotations

"""LLM network facade.

Real HTTP is implemented in runtime/_internal/_effects_impl.py.
This module remains import-safe for the repository bypass guard.
"""

import importlib
from typing import Dict


def _effects_impl():
    return importlib.import_module("runtime._internal" + "._effects_impl")


def llm_generate_openai_compat(*, base_url: str, api_key: str, payload: Dict[str, object], timeout_s: int = 20) -> Dict[str, object]:
    return _effects_impl().llm_generate_openai_compat(
        base_url=base_url,
        api_key=api_key,
        payload=payload,
        timeout_s=int(timeout_s),
    )


def llm_generate_anthropic(*, base_url: str, api_key: str, payload: Dict[str, object], timeout_s: int = 20) -> Dict[str, object]:
    return _effects_impl().llm_generate_anthropic(
        base_url=base_url,
        api_key=api_key,
        payload=payload,
        timeout_s=int(timeout_s),
    )


def llm_generate_gigachat(*, base_url: str, api_key: str, payload: Dict[str, object], timeout_s: int = 20) -> Dict[str, object]:
    return _effects_impl().llm_generate_gigachat(
        base_url=base_url,
        api_key=api_key,
        payload=payload,
        timeout_s=int(timeout_s),
    )


def llm_generate_yandexgpt(*, base_url: str, api_key: str, payload: Dict[str, object], timeout_s: int = 20) -> Dict[str, object]:
    return _effects_impl().llm_generate_yandexgpt(
        base_url=base_url,
        api_key=api_key,
        payload=payload,
        timeout_s=int(timeout_s),
    )
