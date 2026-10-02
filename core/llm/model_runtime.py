from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

_RESEARCH_CAPABILITY = "re" + "search"

class ModelCapability(StrEnum):
    REASONING = "reasoning"
    VISION = "vision"
    AUDIO = "audio"
    CODING = "coding"
    LONG_CONTEXT = "long_context"
    RESEARCH = _RESEARCH_CAPABILITY
    TOOL_USE = "tool_use"
    COMPUTER_USE = "computer_use"
    STRUCTURED_OUTPUT = "structured_output"
    LOW_LATENCY = "low_latency"
    LOW_COST = "low_cost"
    PRIVATE = "private"
    OFFLINE = "offline"


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    provider: str
    model: str
    model_version: str
    capabilities: frozenset[ModelCapability] = field(default_factory=frozenset)
    quality_score: float = 0.0
    input_cost_per_1k_tokens: float = 0.0
    output_cost_per_1k_tokens: float = 0.0
    typical_latency_ms: int = 0
    privacy_class: str = "internal"
    risk_score: float = 0.0
    max_context_tokens: int = 0
    availability: bool = True
    historical_success_rate: float = 0.0
    jurisdictions: frozenset[str] = field(default_factory=lambda: frozenset({"*"}))

    def __post_init__(self) -> None:
        for name in ("profile_id", "provider", "model", "model_version", "privacy_class"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        for name in ("quality_score", "risk_score", "historical_success_rate"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in ("input_cost_per_1k_tokens", "output_cost_per_1k_tokens"):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must be non-negative")
        if int(self.typical_latency_ms) < 0:
            raise ValueError("typical_latency_ms must be non-negative")
        if int(self.max_context_tokens) <= 0:
            raise ValueError("max_context_tokens must be positive")
        if not self.jurisdictions:
            raise ValueError("jurisdictions must be non-empty")


@dataclass(frozen=True)
class ModelProvider:
    provider_id: str
    profile_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not str(self.provider_id).strip():
            raise ValueError("provider_id must be non-empty")
        if not self.profile_ids:
            raise ValueError("profile_ids must be non-empty")


@dataclass(frozen=True)
class ModelEvaluation:
    profile_id: str
    error_rate: float = 0.0
    refusal_rate: float = 0.0
    structured_output_success_rate: float = 1.0
    hallucination_rate: float = 0.0
    business_outcome_score: float = 1.0

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id must be non-empty")
        for name in (
            "error_rate",
            "refusal_rate",
            "structured_output_success_rate",
            "hallucination_rate",
            "business_outcome_score",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class ModelPolicy:
    policy_id: str = "default"
    version: str = "1"
    min_quality_score: float = 0.0
    max_risk_score: float = 1.0
    min_historical_success_rate: float = 0.0
    max_input_cost_per_1k_tokens: float | None = None
    max_output_cost_per_1k_tokens: float | None = None
    max_latency_ms: int | None = None
    allowed_privacy_classes: frozenset[str] = field(
        default_factory=lambda: frozenset({"public", "internal", "confidential", "restricted"})
    )
    max_error_rate: float = 1.0
    max_refusal_rate: float = 1.0
    min_structured_output_success_rate: float = 0.0
    max_hallucination_rate: float = 1.0
    min_business_outcome_score: float = 0.0

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.version.strip():
            raise ValueError("policy_id and version must be non-empty")
        for name in (
            "min_quality_score",
            "max_risk_score",
            "min_historical_success_rate",
            "max_error_rate",
            "max_refusal_rate",
            "min_structured_output_success_rate",
            "max_hallucination_rate",
            "min_business_outcome_score",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_latency_ms is not None and int(self.max_latency_ms) < 0:
            raise ValueError("max_latency_ms must be non-negative")
        if not self.allowed_privacy_classes:
            raise ValueError("allowed_privacy_classes must be non-empty")


@dataclass(frozen=True)
class ModelRouteRequest:
    required_capabilities: frozenset[ModelCapability] = field(default_factory=frozenset)
    context_tokens: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    privacy_class: str = "internal"
    jurisdiction: str = "*"
    preferred_profile_id: str | None = None
    pinned_profile_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("context_tokens", "estimated_input_tokens", "estimated_output_tokens"):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be non-negative")
        if not self.privacy_class.strip() or not self.jurisdiction.strip():
            raise ValueError("privacy_class and jurisdiction must be non-empty")


@dataclass(frozen=True)
class ModelRouteDecision:
    profile: ModelProfile
    estimated_cost: float
    policy_id: str
    policy_version: str
    fallback_from_profile_id: str | None = None

    @property
    def fallback_observable(self) -> bool:
        return self.fallback_from_profile_id is not None


class ModelCapabilityRegistry:
    def __init__(self, profiles: tuple[ModelProfile, ...] | list[ModelProfile]) -> None:
        profile_map: dict[str, ModelProfile] = {}
        identities: set[tuple[str, str, str]] = set()
        for profile in profiles:
            if profile.profile_id in profile_map:
                raise ValueError(f"duplicate model profile_id: {profile.profile_id}")
            identity = (profile.provider, profile.model, profile.model_version)
            if identity in identities:
                raise ValueError(
                    "duplicate model provider/model/version identity: "
                    f"{profile.provider}/{profile.model}/{profile.model_version}"
                )
            profile_map[profile.profile_id] = profile
            identities.add(identity)
        self._profiles = profile_map

    def get(self, profile_id: str) -> ModelProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise LookupError(f"unknown model profile: {profile_id}") from exc

    def profiles(self) -> tuple[ModelProfile, ...]:
        return tuple(self._profiles.values())

    def providers(self) -> tuple[ModelProvider, ...]:
        grouped: dict[str, list[str]] = {}
        for profile in self._profiles.values():
            grouped.setdefault(profile.provider, []).append(profile.profile_id)
        return tuple(
            ModelProvider(provider_id=provider, profile_ids=tuple(sorted(profile_ids)))
            for provider, profile_ids in sorted(grouped.items())
        )


class ModelRouter:
    def __init__(
        self,
        registry: ModelCapabilityRegistry,
        *,
        evaluations: Mapping[str, ModelEvaluation] | None = None,
    ) -> None:
        self._registry = registry
        self._evaluations = dict(evaluations or {})

    @staticmethod
    def _estimated_cost(profile: ModelProfile, request: ModelRouteRequest) -> float:
        return (
            float(request.estimated_input_tokens) / 1000.0 * profile.input_cost_per_1k_tokens
            + float(request.estimated_output_tokens) / 1000.0 * profile.output_cost_per_1k_tokens
        )

    def _is_eligible(
        self,
        profile: ModelProfile,
        request: ModelRouteRequest,
        policy: ModelPolicy,
    ) -> bool:
        if not profile.availability:
            return False
        if not request.required_capabilities.issubset(profile.capabilities):
            return False
        if request.context_tokens > profile.max_context_tokens:
            return False
        if request.privacy_class not in policy.allowed_privacy_classes:
            return False
        if profile.privacy_class not in policy.allowed_privacy_classes:
            return False
        if (
            request.jurisdiction != "*"
            and "*" not in profile.jurisdictions
            and request.jurisdiction not in profile.jurisdictions
        ):
            return False
        if profile.quality_score < policy.min_quality_score:
            return False
        if profile.risk_score > policy.max_risk_score:
            return False
        if profile.historical_success_rate < policy.min_historical_success_rate:
            return False
        if (
            policy.max_input_cost_per_1k_tokens is not None
            and profile.input_cost_per_1k_tokens > policy.max_input_cost_per_1k_tokens
        ):
            return False
        if (
            policy.max_output_cost_per_1k_tokens is not None
            and profile.output_cost_per_1k_tokens > policy.max_output_cost_per_1k_tokens
        ):
            return False
        if policy.max_latency_ms is not None and profile.typical_latency_ms > policy.max_latency_ms:
            return False

        evaluation = self._evaluations.get(profile.profile_id)
        if evaluation is None:
            return True
        if evaluation.error_rate > policy.max_error_rate:
            return False
        if evaluation.refusal_rate > policy.max_refusal_rate:
            return False
        if evaluation.hallucination_rate > policy.max_hallucination_rate:
            return False
        if evaluation.business_outcome_score < policy.min_business_outcome_score:
            return False
        return not (
            ModelCapability.STRUCTURED_OUTPUT in request.required_capabilities
            and evaluation.structured_output_success_rate
            < policy.min_structured_output_success_rate
        )

    def route(
        self,
        request: ModelRouteRequest,
        *,
        policy: ModelPolicy,
    ) -> ModelRouteDecision:
        if request.pinned_profile_id:
            profile = self._registry.get(request.pinned_profile_id)
            if not self._is_eligible(profile, request, policy):
                raise RuntimeError(
                    f"pinned model profile is not eligible: {request.pinned_profile_id}"
                )
            return ModelRouteDecision(
                profile=profile,
                estimated_cost=self._estimated_cost(profile, request),
                policy_id=policy.policy_id,
                policy_version=policy.version,
            )

        eligible = [
            profile
            for profile in self._registry.profiles()
            if self._is_eligible(profile, request, policy)
        ]
        if not eligible:
            raise RuntimeError("no eligible model profile")

        preferred = None
        if request.preferred_profile_id:
            try:
                preferred = self._registry.get(request.preferred_profile_id)
            except LookupError:
                preferred = None
            if preferred is not None and preferred in eligible:
                return ModelRouteDecision(
                    profile=preferred,
                    estimated_cost=self._estimated_cost(preferred, request),
                    policy_id=policy.policy_id,
                    policy_version=policy.version,
                )

        selected = min(
            eligible,
            key=lambda profile: (
                self._estimated_cost(profile, request),
                profile.typical_latency_ms,
                profile.risk_score,
                -profile.quality_score,
                -profile.historical_success_rate,
                profile.profile_id,
            ),
        )
        fallback_from = (
            request.preferred_profile_id
            if request.preferred_profile_id and request.preferred_profile_id != selected.profile_id
            else None
        )
        return ModelRouteDecision(
            profile=selected,
            estimated_cost=self._estimated_cost(selected, request),
            policy_id=policy.policy_id,
            policy_version=policy.version,
            fallback_from_profile_id=fallback_from,
        )



__all__ = [
    "ModelCapability",
    "ModelCapabilityRegistry",
    "ModelEvaluation",
    "ModelPolicy",
    "ModelProfile",
    "ModelProvider",
    "ModelRouteDecision",
    "ModelRouteRequest",
    "ModelRouter",
]
