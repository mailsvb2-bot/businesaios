from __future__ import annotations

"""Canonical training observability surface with compat alias submodules."""

class CheckpointMetrics:
    def summarize(self, saves: int) -> dict[str, int]:
        return {"checkpoint_saves": saves}

class ConvergenceMetrics:
    def summarize(self, converged: bool) -> dict[str, int]:
        return {"converged": int(converged)}

class GradientMetrics:
    def summarize(self, gradients: list[float]) -> dict[str, float]:
        if not gradients:
            return {"gradient_norm": 0.0}
        return {"gradient_norm": sum(abs(value) for value in gradients) / len(gradients)}

class OptimizerMetrics:
    def summarize(self, lr: float) -> dict[str, float]:
        return {"learning_rate": lr}

class TrainMetricsView:
    def summarize(self, losses: list[float]) -> dict[str, float]:
        if not losses:
            return {"loss": 0.0}
        return {"loss": sum(losses) / len(losses)}

_ALIAS_EXPORTS = {
    "checkpoint_metrics": "CheckpointMetrics",
    "convergence_metrics": "ConvergenceMetrics",
    "gradient_metrics": "GradientMetrics",
    "optimizer_metrics": "OptimizerMetrics",
    "train_metrics": "TrainMetricsView",
}

__all__ = [
    "CheckpointMetrics",
    "ConvergenceMetrics",
    "GradientMetrics",
    "OptimizerMetrics",
    "TrainMetricsView",
] + list(_ALIAS_EXPORTS)
