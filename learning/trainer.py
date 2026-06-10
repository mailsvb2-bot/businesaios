from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.numbers import coerce_float
from shared.result import Result

from .outcome_math import OutcomeMathSupport
from .registry import ArtifactRegistry, ModelArtifact, _stable_hash
from .replay import EventStore


@dataclass(frozen=True)
class DatasetSnapshot:
    snapshot_id: str
    start_ts_ms: int
    end_ts_ms: int
    schema_version: int
    rows: List[Dict[str, Any]]
    path: Optional[Path] = None


class DatasetBuilder:
    def __init__(self, store: EventStore, *, schema_version: int = 1, out_dir: Optional[Path] = None) -> None:
        self._store = store
        self._schema_version = int(schema_version)
        self._out_dir = Path(out_dir) if out_dir is not None else None
        if self._out_dir is not None:
            self._out_dir.mkdir(parents=True, exist_ok=True)

    def build(self, start_ts_ms: int, end_ts_ms: int) -> DatasetSnapshot:
        events = self._store.load(int(start_ts_ms), int(end_ts_ms))
        rows: List[Dict[str, Any]] = []
        for e in events:
            if e.event_type != "reward_observed":
                continue
            rows.append({
                "ts_ms": int(e.ts_ms),
                "decision_id": e.decision_id,
                "policy_id": str(e.payload.get("policy_id") or ""),
                "reward": float(e.payload.get("reward", 0.0) or 0.0),
                "ltv": float(e.payload.get("ltv", 0.0) or 0.0),
                "context": dict(e.payload.get("context") or {}),
            })
        rows.sort(key=lambda r: (int(r.get("ts_ms") or 0), str(r.get("decision_id") or "")))
        meta = {
            "start_ts_ms": int(start_ts_ms),
            "end_ts_ms": int(end_ts_ms),
            "schema_version": self._schema_version,
            "rows": rows,
        }
        snapshot_id = _stable_hash(meta)
        snap = DatasetSnapshot(snapshot_id=snapshot_id, start_ts_ms=int(start_ts_ms), end_ts_ms=int(end_ts_ms), schema_version=self._schema_version, rows=rows)
        if self._out_dir is not None:
            path = self._out_dir / f"{snapshot_id}.json"
            path.write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            return DatasetSnapshot(**{**snap.__dict__, "path": path})
        return snap


@dataclass(frozen=True)
class TrainResult:
    model: ModelArtifact


@dataclass(frozen=True)
class PolicyMeanScore:
    policy_id: str
    mean_reward: float
    explanation: str = "offline_mean_reward_score_only"


def score_policies(snapshot: DatasetSnapshot) -> tuple[PolicyMeanScore, ...]:
    by_policy: Dict[str, List[float]] = {}
    for r in snapshot.rows:
        pid = str(r.get("policy_id") or "")
        if not pid:
            continue
        by_policy.setdefault(pid, []).append(float(r.get("reward") or 0.0))
    scored: list[PolicyMeanScore] = []
    for pid, vals in by_policy.items():
        if not vals:
            continue
        scored.append(PolicyMeanScore(policy_id=str(pid), mean_reward=float(sum(vals) / len(vals))))
    return tuple(scored)


class OfflineTrainer:
    def __init__(self, registry: ArtifactRegistry, *, outcome_math: OutcomeMathSupport | None = None) -> None:
        self._registry = registry
        self._outcome_math = outcome_math or OutcomeMathSupport()

    def train(self, snapshot: DatasetSnapshot) -> TrainResult:
        by_policy: Dict[str, List[float]] = {}
        for r in snapshot.rows:
            pid = str(r.get("policy_id") or "")
            if not pid:
                continue
            by_policy.setdefault(pid, []).append(float(r.get("reward") or 0.0))
        if not by_policy:
            metrics = {"offline_mean_reward": 0.0, "n": 0.0, "uplift": 0.0, "conversion_probability_30d": 0.0}
            payload: Dict[str, Any] = {"type": "best_policy_by_mean_reward_v1", "best_policy_id": ""}
            art = self._registry.register(snapshot_id=snapshot.snapshot_id, algo="best_policy_by_mean_reward_v1", metrics=metrics, payload=payload)
            return TrainResult(model=art)
        means: Dict[str, float] = {item.policy_id: item.mean_reward for item in score_policies(snapshot)}
        ordered = sorted(means.items(), key=lambda kv: kv[1], reverse=True)
        best_policy_id = ordered[0][0]
        rewards = [float(r.get("reward") or 0.0) for r in snapshot.rows]
        mean_reward = sum(rewards) / max(1, len(rewards))
        uplift = 0.0
        if len(ordered) >= 2:
            best_rows = [float(r.get("reward") or 0.0) for r in snapshot.rows if str(r.get("policy_id") or "") == ordered[0][0]]
            second_rows = [float(r.get("reward") or 0.0) for r in snapshot.rows if str(r.get("policy_id") or "") == ordered[1][0]]
            if best_rows and second_rows:
                uplift = self._outcome_math.uplift(treatment_outcomes=best_rows, control_outcomes=second_rows)
        conversion_probability_30d = self._outcome_math.conversion_probability(rate_lambda=max(mean_reward, 0.0) / 30.0, horizon_days=30.0)
        payload = {
            "type": "best_policy_by_mean_reward_v1",
            "best_policy_id": str(best_policy_id),
            "policy_means": {k: float(v) for k, v in means.items()},
        }
        metrics = {"offline_mean_reward": float(mean_reward), "n": float(len(rewards)), "uplift": float(uplift), "conversion_probability_30d": float(conversion_probability_30d)}
        art = self._registry.register(snapshot_id=snapshot.snapshot_id, algo="best_policy_by_mean_reward_v1", metrics=metrics, payload=payload)
        return TrainResult(model=art)


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    metrics: Dict[str, float]
    reason: str | None = None


class PolicyValidator:
    MIN_REWARD = 0.0
    MAX_DROP = 0.2

    def validate(self, model_path: Path, baseline_path: Optional[Path] = None) -> ValidationReport:
        policy = json.loads(Path(model_path).read_text(encoding="utf-8"))
        avg_reward = sum(policy.values()) / max(len(policy), 1)
        if avg_reward < self.MIN_REWARD:
            return ValidationReport(False, {"avg_reward": float(avg_reward)}, "reward < 0")
        if baseline_path and Path(baseline_path).exists():
            baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
            drop = self._compute_drop(policy, baseline)
            if drop > self.MAX_DROP:
                return ValidationReport(False, {"drop": float(drop)}, "too much regression")
        return ValidationReport(True, {"avg_reward": float(avg_reward)})

    def _compute_drop(self, new: Dict[str, float], base: Dict[str, float]) -> float:
        keys = set(new) & set(base)
        if not keys:
            return 0.0
        diffs = [float(base[k]) - float(new[k]) for k in keys]
        return max(0.0, sum(diffs) / len(diffs))


@dataclass(frozen=True)
class ValidationVerdict:
    ok: bool
    reason: str | None
    safe_rollout_pct: int


class PolicyValidatorV14:
    def __init__(self, *, min_improvement: float = 0.0, min_n: int = 100) -> None:
        self._min_improvement = float(min_improvement)
        self._min_n = int(min_n)

    def validate(self, candidate: ModelArtifact, baseline_metrics: Dict[str, float]) -> ValidationVerdict:
        n = int(candidate.metrics.get("n", 0))
        if n < self._min_n:
            return ValidationVerdict(False, "insufficient_samples", 0)
        cand = float(candidate.metrics.get("offline_mean_reward", 0.0))
        base = float(baseline_metrics.get("offline_mean_reward", 0.0))
        if cand + self._min_improvement < base:
            return ValidationVerdict(False, "regression_offline", 0)
        return ValidationVerdict(True, None, safe_rollout_pct=10)


@dataclass(frozen=True)
class ValidationScoreView:
    metric_name: str
    metric_value: float
    explanation: str


def build_validation_score_view(*, avg_reward: float, baseline_drop: float | None = None) -> tuple[ValidationScoreView, ...]:
    out = [ValidationScoreView(metric_name="avg_reward", metric_value=float(avg_reward), explanation="validation_metric_only")]
    if baseline_drop is not None:
        out.append(ValidationScoreView(metric_name="baseline_drop", metric_value=float(baseline_drop), explanation="validation_metric_only"))
    return tuple(out)


@dataclass(frozen=True)
class TrainingJob:
    job_id: str
    model_name: str
    dataset_name: str
    metadata: Dict[str, str] = field(default_factory=dict)


class OfflineTraining:
    def run(self, job: object) -> Result:
        job_id = str(getattr(job, "job_id", "") or "").strip()
        model_name = str(getattr(job, "model_name", "") or "").strip()
        dataset_name = str(getattr(job, "dataset_name", "") or "").strip()
        metadata = getattr(job, "metadata", {})
        if not job_id:
            return Result.failure(code="offline_training_missing_job_id", message="training job requires job_id")
        if not model_name:
            return Result.failure(code="offline_training_missing_model_name", message="training job requires model_name", job_id=job_id)
        if not dataset_name:
            return Result.failure(code="offline_training_missing_dataset_name", message="training job requires dataset_name", job_id=job_id, model_name=model_name)
        if metadata is not None and not isinstance(metadata, dict):
            return Result.failure(code="offline_training_metadata_must_be_dict", message="training job metadata must be a dict", job_id=job_id, model_name=model_name)
        for key, value in dict(metadata or {}).items():
            if not str(key).strip():
                return Result.failure(code="offline_training_empty_metadata_key", message="training metadata keys must be non-empty", job_id=job_id, model_name=model_name)
            if not isinstance(value, str):
                return Result.failure(code="offline_training_metadata_values_must_be_strings", message="training metadata values must be strings", job_id=job_id, model_name=model_name)
        return Result.success(code="offline_training_scheduled", job=job)


class TrainingValidation:
    def validate_metrics(self, metrics: dict | None) -> tuple[bool, list[str]]:
        if not isinstance(metrics, dict):
            return False, ["metrics_must_be_dict"]
        issues: list[str] = []
        accuracy = coerce_float(metrics.get("accuracy"), 0.0)
        coverage = coerce_float(metrics.get("coverage"), 0.0)
        precision = coerce_float(metrics.get("precision"), accuracy)
        recall = coerce_float(metrics.get("recall"), coverage)
        for name, value in (("accuracy", accuracy), ("coverage", coverage), ("precision", precision), ("recall", recall)):
            if value < 0.0 or value > 1.0:
                issues.append(f"{name}_out_of_range")
        if accuracy <= 0.0:
            issues.append("missing_accuracy")
        if coverage < 0.5:
            issues.append("coverage_too_low")
        if precision < 0.4:
            issues.append("precision_too_low")
        if recall < 0.4:
            issues.append("recall_too_low")
        return not issues, issues
