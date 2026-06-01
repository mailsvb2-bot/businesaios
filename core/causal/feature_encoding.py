from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from config.feature_encoding_policy import DEFAULT_FEATURE_ENCODING_POLICY, FeatureEncodingPolicy


@dataclass(frozen=True)
class EncodedMatrix:
    """A very small dense design matrix.

    - x: list of rows, each row is list[float]
    - columns: names aligned with x columns

    This intentionally avoids numpy dependency.
    """

    x: list[list[float]]
    columns: list[str]


def _is_number(v: Any) -> bool:
    try:
        float(v)
        return True
    except Exception:
        return False


def _safe_float(v: Any, *, policy: FeatureEncodingPolicy = DEFAULT_FEATURE_ENCODING_POLICY) -> float:
    try:
        f = float(v)
    except Exception:
        return float(policy.numeric_fallback)
    if math.isnan(f) or math.isinf(f):
        return float(policy.numeric_fallback)
    return f


def build_feature_encoder(
    *,
    covariate_names: Sequence[str],
    categorical_limit: int | None = None,
    policy: FeatureEncodingPolicy = DEFAULT_FEATURE_ENCODING_POLICY,
) -> FeatureEncoder:
    limit = policy.categorical_limit if categorical_limit is None else int(categorical_limit)
    return FeatureEncoder(covariate_names=list(covariate_names), categorical_limit=int(limit), policy=policy)


@dataclass
class FeatureEncoder:
    """Encodes flat covariates into a numeric design matrix.

    Strategy:
    - numeric -> pass-through
    - bool -> 0/1
    - categorical strings -> one-hot, capped by categorical_limit per feature

    This is *not* a full ML feature pipeline; it's just enough for simple
    propensity/outcome regressions without external deps.
    """

    covariate_names: list[str]
    categorical_limit: int = DEFAULT_FEATURE_ENCODING_POLICY.categorical_limit
    policy: FeatureEncodingPolicy = DEFAULT_FEATURE_ENCODING_POLICY

    _cat_values: dict[str, list[str]] = None  # type: ignore

    def observe(self, rows: Iterable[Mapping[str, Any]]) -> None:
        self._cat_values = {}
        for name in self.covariate_names:
            values: list[str] = []
            for r in rows:
                v = r.get(name)
                if v is None:
                    continue
                if isinstance(v, bool) or _is_number(v):
                    continue
                s = str(v)
                if s and s not in values:
                    values.append(s)
                if len(values) >= int(self.categorical_limit):
                    break
            self._cat_values[name] = values

    def columns(self) -> list[str]:
        cols: list[str] = ["intercept"]
        for name in self.covariate_names:
            cats = (self._cat_values or {}).get(name) or []
            if cats:
                for c in cats:
                    cols.append(f"{name}={c}")
            else:
                cols.append(name)
        return cols

    def transform(self, rows: Sequence[Mapping[str, Any]]) -> EncodedMatrix:
        if self._cat_values is None:
            self.observe(rows)
        cols = self.columns()
        x: list[list[float]] = []
        for r in rows:
            row: list[float] = [float(self.policy.intercept_value)]  # intercept
            for name in self.covariate_names:
                cats = (self._cat_values or {}).get(name) or []
                v = r.get(name)
                if cats:
                    s = "" if v is None else str(v)
                    for c in cats:
                        row.append(float(self.policy.one_hot_match_value) if s == c else float(self.policy.one_hot_miss_value))
                else:
                    if isinstance(v, bool):
                        row.append(float(self.policy.true_value) if v else float(self.policy.false_value))
                    else:
                        row.append(_safe_float(v, policy=self.policy))
            x.append(row)
        return EncodedMatrix(x=x, columns=cols)


def encode_covariates(
    covariates: Sequence[Mapping[str, Any]],
    *,
    covariate_names: Sequence[str],
    categorical_limit: int | None = None,
    policy: FeatureEncodingPolicy = DEFAULT_FEATURE_ENCODING_POLICY,
) -> EncodedMatrix:
    enc = build_feature_encoder(covariate_names=covariate_names, categorical_limit=categorical_limit, policy=policy)
    enc.observe(covariates)
    return enc.transform(list(covariates))
