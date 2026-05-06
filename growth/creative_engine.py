from __future__ import annotations

from growth.engine_base import GrowthEngineSurface
from growth.engine_contract import CREATIVE_ENGINE_PACKAGE_KIND, build_package


class CreativeEngine(GrowthEngineSurface):

    def build_creative_brief(self, payload: dict | None) -> dict:
        return self.artifact("creative_brief", payload)

    def plan_creative_variants(self, payload: dict | None) -> dict:
        return self.artifact("creative_variants", payload)

    def build_landing_copy(self, payload: dict | None) -> dict:
        return self.artifact("landing_copy", payload)

    def build_cta_variants(self, payload: dict | None) -> dict:
        return self.artifact("cta_variants", payload)

    def build_form_variants(self, payload: dict | None) -> dict:
        return self.artifact("form_variants", payload)

    def select_layout(self, payload: dict | None) -> dict:
        return self.artifact("layout_choice", payload)

    def resolve_landing_template(self, payload: dict | None) -> dict:
        return self.artifact("landing_template", payload)

    def build_landing_page(self, payload: dict | None) -> dict:
        return self.artifact("landing_page", payload)

    def publish_landing(self, payload: dict | None) -> dict:
        return self.artifact("publish_request", payload)

    def plan_ab_test(self, payload: dict | None) -> dict:
        return self.artifact("landing_ab_test", payload)

    def build_local_proof_blocks(self, payload: dict | None) -> dict:
        return self.artifact("local_proof_blocks", payload)

    def assemble_landing(self, payload: dict | None) -> dict:
        normalized = self.payload(payload)
        return build_package(
            CREATIVE_ENGINE_PACKAGE_KIND,
            normalized,
            creative_brief=self.build_creative_brief(normalized),
            creative_variants=self.plan_creative_variants(normalized),
            landing_copy=self.build_landing_copy(normalized),
            cta_variants=self.build_cta_variants(normalized),
            form_variants=self.build_form_variants(normalized),
            layout=self.select_layout(normalized),
            landing_template=self.resolve_landing_template(normalized),
            landing_page=self.build_landing_page(normalized),
            landing_publish=self.publish_landing(normalized),
            ab_test=self.plan_ab_test(normalized),
            local_proof_blocks=self.build_local_proof_blocks(normalized),
        )


class CreativeBriefBuilder:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_creative_brief(payload)


class CreativeVariantPlanner:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def plan(self, payload: dict) -> dict:
        return self._engine.plan_creative_variants(payload)


class CtaVariantBuilder:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_cta_variants(payload)


class FormVariantBuilder:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_form_variants(payload)


class LandingAbTestPlanner:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def plan(self, payload: dict) -> dict:
        return self._engine.plan_ab_test(payload)


class LandingCopyBuilder:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_landing_copy(payload)


class LandingLayoutSelector:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def select(self, payload: dict) -> dict:
        return self._engine.select_layout(payload)


class LandingPageFactory:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_landing_page(payload)


class LandingPublishService:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def publish(self, payload: dict) -> dict:
        return self._engine.publish_landing(payload)


class LandingTemplateRegistry:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def resolve(self, payload: dict) -> dict:
        return self._engine.resolve_landing_template(payload)


class LocalProofBlockBuilder:
    def __init__(self, *, engine: CreativeEngine | None = None) -> None:
        self._engine = engine or CreativeEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_local_proof_blocks(payload)


__all__ = [
    "CreativeBriefBuilder",
    "CreativeEngine",
    "CreativeVariantPlanner",
    "CtaVariantBuilder",
    "FormVariantBuilder",
    "LandingAbTestPlanner",
    "LandingCopyBuilder",
    "LandingLayoutSelector",
    "LandingPageFactory",
    "LandingPublishService",
    "LandingTemplateRegistry",
    "LocalProofBlockBuilder",
]
