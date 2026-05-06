from __future__ import annotations

"""Canonical policy model factory surface with compat alias submodules."""

class BackboneFactory:
    def create(self, builder, **kwargs):
        return builder(**kwargs)

class DecoderFactory:
    def create(self, builder, **kwargs):
        return builder(**kwargs)

class EmbeddingFactory:
    def create(self, builder, **kwargs):
        return builder(**kwargs)

class EncoderFactory:
    def create(self, builder, **kwargs):
        return builder(**kwargs)

class HeadFactory:
    def create(self, builder, **kwargs):
        return builder(**kwargs)

def initialize_parameters(params, value: float = 0.0) -> None:
    for param in params:
        if hasattr(param, "data"):
            param.data.fill_(value)

class ModelFactory:
    def create(self, builder, **kwargs):
        return builder(**kwargs)

class NormalizationFactory:
    def create(self, builder, **kwargs):
        return builder(**kwargs)

def parameter_groups(model) -> list[dict]:
    if hasattr(model, "parameters"):
        return [{"params": list(model.parameters())}]
    return []

__all__ = [
    "BackboneFactory",
    "DecoderFactory",
    "EmbeddingFactory",
    "EncoderFactory",
    "HeadFactory",
    "initialize_parameters",
    "ModelFactory",
    "NormalizationFactory",
    "parameter_groups",
    "backbone_factory",
    "decoder_factory",
    "embedding_factory",
    "encoder_factory",
    "head_factory",
    "initialization",
    "model_factory",
    "normalization_factory",
    "parameter_groups",
]
