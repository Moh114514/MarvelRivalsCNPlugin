"""Small, deterministic transforms used by Rating V2."""

from __future__ import annotations

import math
from statistics import median
from collections.abc import Iterable


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def robust_z(value: float, population: Iterable[float], *, epsilon: float = 1e-9) -> float:
    """Return the documented median/MAD robust z-score.

    A flat population has no evidence of separation, so it is centered at
    zero rather than producing an arbitrary extreme score.
    """

    values = [float(item) for item in population]
    if not values:
        return 0.0
    center = median(values)
    mad = median([abs(item - center) for item in values])
    scale = 1.4826 * mad
    if scale <= epsilon:
        return 0.0 if abs(float(value) - center) <= epsilon else math.copysign(3.0, float(value) - center)
    return max(-3.0, min(3.0, (float(value) - center) / (scale + epsilon)))


def robust_score(value: float, population: Iterable[float], *, max_z: float = 3.0) -> float:
    z = robust_z(value, population)
    z = max(-float(max_z), min(float(max_z), z))
    return clamp(50.0 + 50.0 * math.tanh(z / 2.0))


def saturating(value: float | None, scale: float) -> float:
    if value is None or scale <= 0:
        return 0.0
    return clamp(1.0 - math.exp(-max(0.0, float(value)) / scale), 0.0, 1.0)


def weighted_mean(values: Iterable[tuple[float | None, float]]) -> float | None:
    numerator = denominator = 0.0
    for value, weight in values:
        if value is None or weight <= 0:
            continue
        numerator += float(value) * float(weight)
        denominator += float(weight)
    return numerator / denominator if denominator else None
