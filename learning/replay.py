from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, List, Optional, Protocol, Sequence, Tuple, TypeVar

from contracts.event_store import EventStoreReader, iter_events_strict


@dataclass(frozen=True)
class Event:
    event_id: str
    ts_ms: int
    user_id: str
    source: str
    event_type: str
    decision_id: Optional[str]
    payload: Dict[str, Any]


class OfflineEventStore(Protocol):
    def load(self, start_ts_ms: int, end_ts_ms: int) -> List[Event]: ...
    def append(self, e: Event) -> None: ...


class RuntimeEventStoreAdapter:
    """Adapter over the canonical runtime event store (iter_events API)."""

    def __init__(self, platform_store: EventStoreReader, *, tenant_id: str = "default") -> None:
        self._store = platform_store
        self._tenant_id = str(tenant_id or "default")

    def load(self, start_ts_ms: int, end_ts_ms: int) -> List[Event]:
        rows = list(iter_events_strict(self._store, tenant_id=self._tenant_id, start_ms=int(start_ts_ms), end_ms=int(end_ts_ms)))
        rows.sort(key=lambda e: (int(e.get("timestamp_ms") or 0), str(e.get("event_id") or "")))
        out: List[Event] = []
        for r in rows:
            out.append(
                Event(
                    event_id=str(r.get("event_id") or ""),
                    ts_ms=int(r.get("timestamp_ms") or 0),
                    user_id=str(r.get("user_id") or ""),
                    source=str(r.get("source") or ""),
                    event_type=str(r.get("event_type") or r.get("type") or ""),
                    decision_id=(str(r.get("decision_id")) if r.get("decision_id") is not None else None),
                    payload=dict(r.get("payload") or {}),
                )
            )
        return out

    def append(self, e: Event) -> None:
        append = getattr(self._store, "append_event", None)
        if not callable(append):
            raise TypeError("platform_store does not support append_event()")
        append(
            {
                "event_id": e.event_id,
                "timestamp_ms": e.ts_ms,
                "user_id": e.user_id,
                "source": e.source,
                "event_type": e.event_type,
                "decision_id": e.decision_id,
                "payload": dict(e.payload),
                "tenant_id": self._tenant_id,
            }
        )


EventStore = OfflineEventStore

T = TypeVar("T")


@dataclass(frozen=True)
class SplitResult(Generic[T]):
    train: List[T]
    evaluation: List[T]

    def __iter__(self):
        yield self.train
        yield self.evaluation

    def as_tuple(self) -> Tuple[List[T], List[T]]:
        return self.train, self.evaluation


class PolicyDatasetSplitter:
    def __init__(self, seed: int = 42) -> None:
        self._seed = seed

    def split(self, items: Sequence[T], eval_fraction: float = 0.2) -> SplitResult[T]:
        if not 0.0 < eval_fraction < 1.0:
            raise ValueError("eval_fraction must be between 0 and 1.")
        data = list(items)
        if len(data) < 2:
            raise ValueError("At least two items are required to split dataset.")
        rng = random.Random(self._seed)
        rng.shuffle(data)
        split_index = int(len(data) * (1.0 - eval_fraction))
        split_index = max(1, min(split_index, len(data) - 1))
        train = data[:split_index]
        evaluation = data[split_index:]
        if not train or not evaluation:
            raise ValueError("Dataset split failed: one of the splits is empty.")
        return SplitResult(train=train, evaluation=evaluation)


class PolicyProtocol(Protocol):
    def act(self, state: Any) -> Any: ...


@dataclass(frozen=True)
class EvaluationSample:
    state: Any
    reward_function: Callable[[Any], float]


@dataclass(frozen=True)
class EvaluationResult:
    policy_id: str
    mean_reward: float
    reward_std: float
    samples: int

    def __getitem__(self, key: str):
        mapping = {
            "policy_id": self.policy_id,
            "mean_reward": self.mean_reward,
            "reward_mean": self.mean_reward,
            "reward_std": self.reward_std,
            "std": self.reward_std,
            "samples": self.samples,
        }
        return mapping[key]


class PolicyEvaluator:
    def evaluate(self, *args) -> EvaluationResult:
        if len(args) == 2:
            policy = args[0]
            dataset = args[1]
            policy_id = getattr(policy, "policy_id", "anonymous_policy")
        elif len(args) == 3:
            policy_id = str(args[0])
            policy = args[1]
            dataset = args[2]
        else:
            raise TypeError("evaluate expects (policy, dataset) or (policy_id, policy, dataset)")
        rewards: List[float] = []
        for sample in dataset:
            action = policy.act(sample.state)
            reward = float(sample.reward_function(action))
            rewards.append(reward)
        if not rewards:
            raise ValueError("Evaluation dataset is empty.")
        mean_reward = sum(rewards) / len(rewards)
        variance = sum((r - mean_reward) ** 2 for r in rewards) / len(rewards)
        reward_std = math.sqrt(variance)
        return EvaluationResult(policy_id=policy_id, mean_reward=mean_reward, reward_std=reward_std, samples=len(rewards))




class OfflineReplayEvaluator:
    """Deterministic offline replay summary for closed-loop learning.

    Kept in learning.replay so demand-learning surfaces do not carry a parallel
    replay evaluator implementation.
    """

    def evaluate(self, feedback_rows: tuple[dict[str, object], ...]) -> dict[str, float]:
        from config.learning_thresholds import MIN_REPLAY_SAMPLE_SIZE

        converted = sum(1 for row in feedback_rows if row.get("converted"))
        bad_outcomes = sum(
            1
            for row in feedback_rows
            if row.get("returned") or row.get("complaint") or row.get("fraud_flag")
        )
        total = len(feedback_rows)
        effective_total = max(1, total)
        return {
            "offline_conversion_rate": converted / effective_total,
            "offline_bad_outcome_rate": bad_outcomes / effective_total,
            "sample_size": float(total),
            "sample_is_sufficient": 1.0 if total >= MIN_REPLAY_SAMPLE_SIZE else 0.0,
        }

class FeedbackLoopViolation(Exception):
    """Raised when a runaway feedback-loop protection rule is violated."""


@dataclass(frozen=True)
class PolicyMetadata:
    """Minimal metadata required to validate safe training/evaluation/promotion flow."""

    policy_id: str
    trained_at_ms: int
    source_dataset_id: str
    evaluation_dataset_id: Optional[str] = None
    trained_by_component: Optional[str] = None


class FeedbackLoopFirewall:
    """Runtime and pipeline guard against self-reinforcing policy loops."""

    def __init__(self, min_eval_delay_ms: int = 60 * 60 * 1000) -> None:
        self._min_eval_delay_ms = int(min_eval_delay_ms)

    def validate_dataset_separation(self, train_dataset_id: str, eval_dataset_id: str) -> None:
        if not train_dataset_id or not eval_dataset_id:
            raise FeedbackLoopViolation("Both train and eval dataset ids are required.")
        if train_dataset_id == eval_dataset_id:
            raise FeedbackLoopViolation("Training and evaluation datasets must be different.")

    def validate_policy_eval_dataset(self, policy: PolicyMetadata, eval_dataset_id: str) -> None:
        if policy.source_dataset_id == eval_dataset_id:
            raise FeedbackLoopViolation("Policy cannot be evaluated on the same dataset it was trained on.")

    def validate_eval_delay(self, policy: PolicyMetadata, now_ms: Optional[int] = None) -> None:
        import time
        current_ms = int(now_ms) if now_ms is not None else int(time.time() * 1000)
        elapsed_ms = current_ms - int(policy.trained_at_ms)
        if elapsed_ms < self._min_eval_delay_ms:
            raise FeedbackLoopViolation(
                f"Evaluation is too early after training: elapsed={elapsed_ms} ms, required={self._min_eval_delay_ms} ms."
            )

    def validate_component_separation(self, trainer_component: Optional[str], evaluator_component: Optional[str]) -> None:
        if trainer_component and evaluator_component and trainer_component == evaluator_component:
            raise FeedbackLoopViolation("Trainer and evaluator components must be separated.")

    def validate_all(
        self,
        policy: PolicyMetadata,
        train_dataset_id: str,
        eval_dataset_id: str,
        trainer_component: Optional[str] = None,
        evaluator_component: Optional[str] = None,
        now_ms: Optional[int] = None,
    ) -> None:
        self.validate_dataset_separation(train_dataset_id, eval_dataset_id)
        self.validate_policy_eval_dataset(policy, eval_dataset_id)
        self.validate_eval_delay(policy, now_ms=now_ms)
        self.validate_component_separation(trainer_component, evaluator_component)

    def validate_datasets(self, train_dataset: str, eval_dataset: str) -> None:
        self.validate_dataset_separation(train_dataset, eval_dataset)

    def validate_policy_evaluation(self, policy: PolicyMetadata, eval_dataset: str) -> None:
        self.validate_policy_eval_dataset(policy, eval_dataset)
