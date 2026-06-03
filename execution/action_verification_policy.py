from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

CANON_ACTION_VERIFICATION_POLICY = True
_MODES = {"auto", "required", "not_required"}
_NOT_REQUIRED = {"advisory", "read_only", "read-only", "readonly", "no_op", "no-op", "noop", "internal_bookkeeping", "internal-bookkeeping", "bookkeeping", "internal_execution"}


def _text(value: object) -> str: return str(value or "").strip()

def _safe_dict(value: object) -> dict[str, Any]: return dict(value) if isinstance(value, Mapping) else {}

def _normalize_mode(value: object, *, default: str = "required") -> str:
    text = _text(value)
    return text if text in _MODES else default


def _normalize_category(value: object) -> str: return _text(value).casefold().replace(" ", "_")


@dataclass(frozen=True, slots=True)
class ActionVerificationPolicy:
    action_type: str
    action_category: str
    external_confirmation_mode: str
    def to_dict(self) -> dict[str, Any]:
        return {"action_type": self.action_type, "action_category": self.action_category, "external_confirmation_mode": self.external_confirmation_mode}


def determine_external_confirmation_mode(action: Mapping[str, Any] | None, *, default_mode: str = "required") -> str:
    payload = _safe_dict(action)
    explicit = _normalize_mode(payload.get("external_confirmation_mode"), default="")
    if explicit in _MODES: return explicit
    category = _normalize_category(payload.get("action_category") or payload.get("effect_category") or payload.get("execution_category") or payload.get("kind"))
    return "not_required" if category in _NOT_REQUIRED else _normalize_mode(default_mode, default="required")


def build_action_verification_policy(action: Mapping[str, Any] | None, *, default_mode: str = "required") -> ActionVerificationPolicy:
    payload = _safe_dict(action)
    category = _normalize_category(payload.get("action_category") or payload.get("effect_category") or payload.get("execution_category") or payload.get("kind"))
    return ActionVerificationPolicy(_text(payload.get("action_type")), category, determine_external_confirmation_mode(payload, default_mode=default_mode))


__all__ = ["CANON_ACTION_VERIFICATION_POLICY", "ActionVerificationPolicy", "determine_external_confirmation_mode", "build_action_verification_policy"]
