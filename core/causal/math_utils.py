from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


def mean(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    return float(sum(xs)) / float(len(xs))


def variance(xs: Sequence[float]) -> float:
    n = len(xs)
    if n <= 1:
        return 0.0
    m = mean(xs)
    return sum((float(x) - m) ** 2 for x in xs) / float(n - 1)


def stderr_of_mean(xs: Sequence[float]) -> float:
    n = len(xs)
    if n <= 1:
        return 0.0
    return math.sqrt(variance(xs) / float(n))


def sigmoid(z: float) -> float:
    # Stable sigmoid
    z = float(z)
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


@dataclass(frozen=True)
class LinRegResult:
    coef: list[float]
    stderr: list[float] | None = None


def _matmul(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    m = len(A)
    n = len(A[0]) if A else 0
    p = len(B[0]) if B else 0
    out = [[0.0 for _ in range(p)] for _ in range(m)]
    for i in range(m):
        for k in range(n):
            aik = A[i][k]
            for j in range(p):
                out[i][j] += aik * B[k][j]
    return out


def _transpose(A: list[list[float]]) -> list[list[float]]:
    if not A:
        return []
    return [list(row) for row in zip(*A, strict=False)]


def _solve_gauss_jordan(M: list[list[float]], b: list[float]) -> list[float]:
    # Solve M x = b using Gauss-Jordan elimination.
    n = len(M)
    A = [list(map(float, row)) + [float(bi)] for row, bi in zip(M, b, strict=False)]

    for col in range(n):
        # pivot
        pivot = None
        best = 0.0
        for r in range(col, n):
            v = abs(A[r][col])
            if v > best:
                best = v
                pivot = r
        if pivot is None or best <= 1e-12:
            # Singular -> return zeros
            return [0.0 for _ in range(n)]
        if pivot != col:
            A[col], A[pivot] = A[pivot], A[col]

        # normalize
        div = A[col][col]
        for j in range(col, n + 1):
            A[col][j] /= div

        # eliminate
        for r in range(n):
            if r == col:
                continue
            factor = A[r][col]
            if abs(factor) <= 1e-12:
                continue
            for j in range(col, n + 1):
                A[r][j] -= factor * A[col][j]

    return [A[i][n] for i in range(n)]


def linear_regression_fit(X: list[list[float]], y: list[float]) -> LinRegResult:
    """OLS via normal equations: beta = (X'X)^-1 X'y.

    Very small, dependency-free implementation.
    """

    if not X:
        return LinRegResult(coef=[])
    n = len(X)
    p = len(X[0])
    if n != len(y):
        raise ValueError("X and y size mismatch")

    Xt = _transpose(X)
    XtX = _matmul(Xt, X)
    Xty_mat = _matmul(Xt, [[float(v)] for v in y])
    Xty = [row[0] for row in Xty_mat]

    coef = _solve_gauss_jordan(XtX, Xty)
    # stderr estimation omitted intentionally (we provide bootstrap elsewhere)
    return LinRegResult(coef=list(coef), stderr=None)


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return float(sum(float(x) * float(y) for x, y in zip(a, b, strict=False)))


def clip(v: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(v)))
