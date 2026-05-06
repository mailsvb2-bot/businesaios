from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

class CheckpointingStep:
    def save_if_needed(self, manager, state, metric: float):
        return manager.maybe_save(state=state, metric=metric)

class Trainable(Protocol):
    def train_step(self, batch) -> dict:
        ...

class ConvergenceDetection:
    def converged(self, losses: list[float], tolerance: float = 1e-3) -> bool:
        if len(losses) < 2:
            return False
        return abs(losses[-1] - losses[-2]) < tolerance

class EarlyStopping:
    def __init__(self, patience: int = 3) -> None:
        self._patience = patience
        self._best: float | None = None
        self._bad_steps = 0

    def update(self, metric: float) -> bool:
        if self._best is None or metric < self._best:
            self._best = metric
            self._bad_steps = 0
            return False
        self._bad_steps += 1
        return self._bad_steps >= self._patience

class GradientAccumulation:
    def __init__(self) -> None:
        self._sum = 0.0
        self._count = 0

    def add(self, loss: float) -> None:
        self._sum += loss
        self._count += 1

    def average(self) -> float:
        return 0.0 if self._count == 0 else self._sum / self._count

    def reset(self) -> None:
        self._sum = 0.0
        self._count = 0

def clip_gradient_norm(value: float, max_norm: float) -> float:
    if abs(value) <= max_norm:
        return value
    return max_norm if value > 0 else -max_norm

class GradientPipeline:
    def backward(self, loss: float) -> float:
        return loss

class LearningRateControl:
    def decay(self, lr: float, factor: float = 0.9) -> float:
        return lr * factor

class MixedPrecision:
    def scale(self, loss: float, factor: float = 1.0) -> float:
        return loss * factor

class OptimizerFactory:
    def create(self, builder, parameters, **kwargs):
        return builder(parameters, **kwargs)

class SchedulerFactory:
    def create(self, builder, optimizer, **kwargs):
        return builder(optimizer, **kwargs)

@dataclass(frozen=True)
class TrainMetrics:
    loss: float
    step: int
    epoch: int

@dataclass
class TrainState:
    epoch: int = 0
    step: int = 0
    best_metric: float | None = None

class TrainStep:
    def run(self, learner, batch, state: TrainState) -> TrainMetrics:
        result = learner.train_step(batch)
        state.step += 1
        return TrainMetrics(loss=float(result.get("total_loss", result.get("loss", 0.0))), step=state.step, epoch=state.epoch)

class TrainEpoch:
    def __init__(self, train_step: TrainStep | None = None) -> None:
        self._train_step = train_step or TrainStep()

    def run(self, learner, batches, state: TrainState):
        metrics = []
        for batch in batches:
            metrics.append(self._train_step.run(learner, batch, state))
        state.epoch += 1
        return metrics

class FitLoop:
    def __init__(self, epoch_runner: TrainEpoch | None = None) -> None:
        self._epoch_runner = epoch_runner or TrainEpoch()

    def run(self, learner, epochs, epoch_batches):
        state = TrainState()
        history = []
        for _ in range(epochs):
            metrics = self._epoch_runner.run(learner, epoch_batches, state)
            history.extend(metrics)
        return history

class LearnerLoop:
    def __init__(self, train_step: TrainStep | None = None, early_stopping: EarlyStopping | None = None) -> None:
        self._train_step = train_step or TrainStep()
        self._early_stopping = early_stopping or EarlyStopping()

    def run(self, learner, batches):
        state = TrainState()
        history = []
        for batch in batches:
            metric = self._train_step.run(learner, batch, state)
            history.append(metric)
            if self._early_stopping.update(metric.loss):
                break
        return history

class Trainer:
    def __init__(self, learner_loop: LearnerLoop | None = None) -> None:
        self._learner_loop = learner_loop or LearnerLoop()

    def fit(self, learner, batches):
        return self._learner_loop.run(learner, batches)

class TrainerFactory:
    def create(self) -> Trainer:
        return Trainer()

_MODULE_EXPORTS = {
    'checkpointing_step': {'CheckpointingStep': 'runtime.platform.support.training:CheckpointingStep'},
    'contracts': {'Trainable': 'runtime.platform.support.training:Trainable'},
    'convergence_detection': {'ConvergenceDetection': 'runtime.platform.support.training:ConvergenceDetection'},
    'early_stopping': {'EarlyStopping': 'runtime.platform.support.training:EarlyStopping'},
    'fit_loop': {'FitLoop': 'runtime.platform.support.training:FitLoop'},
    'gradient_accumulation': {'GradientAccumulation': 'runtime.platform.support.training:GradientAccumulation'},
    'gradient_clipping': {'clip_gradient_norm': 'runtime.platform.support.training:clip_gradient_norm'},
    'gradient_pipeline': {'GradientPipeline': 'runtime.platform.support.training:GradientPipeline'},
    'learner_loop': {'LearnerLoop': 'runtime.platform.support.training:LearnerLoop'},
    'learning_rate_control': {'LearningRateControl': 'runtime.platform.support.training:LearningRateControl'},
    'mixed_precision': {'MixedPrecision': 'runtime.platform.support.training:MixedPrecision'},
    'optimizer_factory': {'OptimizerFactory': 'runtime.platform.support.training:OptimizerFactory'},
    'scheduler_factory': {'SchedulerFactory': 'runtime.platform.support.training:SchedulerFactory'},
    'train_epoch': {'TrainEpoch': 'runtime.platform.support.training:TrainEpoch'},
    'train_metrics': {'TrainMetrics': 'runtime.platform.support.training:TrainMetrics'},
    'train_state': {'TrainState': 'runtime.platform.support.training:TrainState'},
    'train_step': {'TrainStep': 'runtime.platform.support.training:TrainStep'},
    'trainer': {'Trainer': 'runtime.platform.support.training:Trainer'},
    'trainer_factory': {'TrainerFactory': 'runtime.platform.support.training:TrainerFactory'},
}

__all__ = [
    'CheckpointingStep', 'ConvergenceDetection', 'EarlyStopping', 'FitLoop', 'GradientAccumulation',
    'GradientPipeline', 'LearnerLoop', 'LearningRateControl', 'MixedPrecision', 'OptimizerFactory',
    'SchedulerFactory', 'TrainEpoch', 'TrainMetrics', 'TrainState', 'TrainStep', 'Trainable',
    'Trainer', 'TrainerFactory', 'clip_gradient_norm',
]
