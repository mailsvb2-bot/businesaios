"""
LLM interface layer.

This module is intentionally minimal: the project can run without an LLM,
and can operate in template-only mode.
"""

from .base import LLMClient, LLMMessage, LLMResponse
from .templated import TemplatedLLM

__all__ = ["LLMClient", "LLMMessage", "LLMResponse", "TemplatedLLM"]
