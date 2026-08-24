"""Confidence and evidence shrinkage for Rating V2."""

from __future__ import annotations

import math

from .transforms import clamp


def calculate_confidence(
    competitive_matches: int,
    meta_coverage: float,
    observable_coverage: float,
    comparable_seasons: int,
) -> tuple[float, dict[str, float]]:
    sample = 1.0 - math.exp(-max(0, competitive_matches) / 20.0)
    components = {
        "sample": clamp(sample, 0.0, 1.0),
        "meta": clamp(meta_coverage / 100.0, 0.0, 1.0),
        "observable": clamp(observable_coverage / 100.0, 0.0, 1.0),
        "season": clamp(comparable_seasons / 3.0, 0.0, 1.0),
    }
    confidence = (
        0.40 * components["sample"]
        + 0.25 * components["meta"]
        + 0.20 * components["observable"]
        + 0.15 * components["season"]
    )
    return clamp(confidence, 0.0, 1.0), components


def shrink_performance(raw: float, confidence: float) -> float:
    return 50.0 + clamp(confidence, 0.0, 1.0) * (float(raw) - 50.0)
