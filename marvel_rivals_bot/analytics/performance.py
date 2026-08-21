"""Shared signed-performance calculations for personal hero analysis.

This module is the second-round scoring boundary. It owns evidence gates,
delta shrinkage, scores, and the user-facing status axis; command handlers and
renderers must only consume the resulting ViewModels.
"""

from __future__ import annotations

from typing import Any

from .models import AnalysisScope
from .signature_rules import (
    adjust_delta,
    calculate_confidence,
    calculate_performance_sickness_score,
    calculate_stability,
)


ANALYSIS_MIN_TOTAL_MATCHES = 10
ANALYSIS_MIN_COMPETITIVE_MATCHES = 5
ANALYSIS_MIN_QUICK_MATCHES = 20
PERSONAL_COMPETITIVE_PRIOR_MATCHES = 20
PERSONAL_QUICK_PRIOR_MATCHES = 30
PERFORMANCE_NEUTRAL_BAND = 10.0

EVIDENCE_FACTORS = {
    "数据不足": 0.25,
    "低": 0.45,
    "中": 0.70,
    "高": 0.85,
    "很高": 1.00,
}


def adjust_personal_delta(raw_delta: float | None, matches: int, prior_matches: int) -> float | None:
    """Shrink a same-mode leave-one-out delta toward zero."""

    if raw_delta is None:
        return None
    try:
        sample = max(0, int(matches))
        prior = max(0, int(prior_matches))
        if sample == 0:
            return 0.0
        return float(raw_delta) * sample / (sample + prior)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def is_analysis_eligible(*, total_matches: int, competitive_matches: int, quick_matches: int) -> bool:
    """Return whether a hero has enough usage evidence for a ranked view."""

    return (
        max(0, int(total_matches or 0)) >= ANALYSIS_MIN_TOTAL_MATCHES
        or max(0, int(competitive_matches or 0)) >= ANALYSIS_MIN_COMPETITIVE_MATCHES
        or max(0, int(quick_matches or 0)) >= ANALYSIS_MIN_QUICK_MATCHES
    )


def calculate_evidence_factor(confidence: str | None) -> float:
    return EVIDENCE_FACTORS.get(str(confidence or "数据不足"), 0.25)


def _score_from_cap(value: float | None, cap: float) -> float | None:
    if value is None:
        return None
    try:
        return min(100.0, max(0.0, float(value) / cap * 100))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def calculate_play_index(
    competitive_matches: int,
    quick_matches: int,
    usage_share: float,
    *,
    competitive_cap: int = 50,
    quick_cap: int = 50,
) -> float:
    competitive = _score_from_cap(competitive_matches, competitive_cap) or 0.0
    quick = _score_from_cap(quick_matches, quick_cap) or 0.0
    share = _score_from_cap(usage_share, 20) or 0.0
    return round(competitive * 0.40 + quick * 0.20 + share * 0.40, 4)


def _signed_score(value: float | None, cap: float) -> float | None:
    if value is None:
        return None
    try:
        return max(-100.0, min(100.0, float(value) / cap * 100))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def calculate_performance_index(
    *,
    adjusted_meta_delta: float | None = None,
    adjusted_personal_competitive_delta: float | None = None,
    adjusted_personal_quick_delta: float | None = None,
    meta_delta: float | None = None,
    personal_competitive_delta: float | None = None,
    personal_quick_delta: float | None = None,
) -> float:
    """Combine robust signed deltas into a -100..+100 index.

    The old argument names remain accepted for one compatibility cycle; the
    service itself always passes the explicit adjusted values.
    """

    if adjusted_meta_delta is None:
        adjusted_meta_delta = meta_delta
    if adjusted_personal_competitive_delta is None:
        adjusted_personal_competitive_delta = personal_competitive_delta
    if adjusted_personal_quick_delta is None:
        adjusted_personal_quick_delta = personal_quick_delta

    signals = (
        (adjusted_meta_delta, 8.0, 0.55),
        (adjusted_personal_competitive_delta, 8.0, 0.30),
        (adjusted_personal_quick_delta, 10.0, 0.15),
    )
    weighted = 0.0
    weight_total = 0.0
    for value, cap, weight in signals:
        normalized = _signed_score(value, cap)
        if normalized is None:
            continue
        weighted += normalized * weight
        weight_total += weight
    if weight_total <= 0:
        return 0.0
    return round(max(-100.0, min(100.0, weighted / weight_total)), 4)


def calculate_signature_score(play_index: float, performance_index: float, evidence_factor: float = 1.0) -> float:
    return round(
        max(0.0, float(play_index)) * max(0.0, float(performance_index)) / 100
        * max(0.0, min(1.0, float(evidence_factor))),
        4,
    )


def calculate_sickness_score(play_index: float, performance_index: float, evidence_factor: float = 1.0) -> float:
    return round(
        max(0.0, float(play_index)) * max(0.0, -float(performance_index)) / 100
        * max(0.0, min(1.0, float(evidence_factor))),
        4,
    )


def is_signature_candidate(hero: Any) -> bool:
    return bool(
        getattr(hero, "is_analysis_eligible", False)
        and float(getattr(hero, "performance_index", 0.0) or 0.0) >= PERFORMANCE_NEUTRAL_BAND
        and float(getattr(hero, "signature_score", 0.0) or 0.0) > 0
    )


def is_performance_sickness_candidate(hero: Any) -> bool:
    return bool(
        getattr(hero, "is_analysis_eligible", False)
        and float(getattr(hero, "performance_index", 0.0) or 0.0) <= -PERFORMANCE_NEUTRAL_BAND
        and float(getattr(hero, "sickness_score", 0.0) or 0.0) > 0
    )


def _confidence_at_least(value: str, minimum: str) -> bool:
    order = {"数据不足": 0, "低": 1, "中": 2, "高": 3, "很高": 4}
    return order.get(value, 0) >= order[minimum]


def classify_hero_performance(hero: Any, scope: AnalysisScope) -> str:
    """Classify one already-scored hero on the unified signed axis."""

    performance = float(getattr(hero, "performance_index", 0.0) or 0.0)
    score = float(getattr(hero, "signature_score", 0.0) or 0.0)
    eligible = bool(getattr(hero, "is_analysis_eligible", False))
    confidence = str(getattr(hero, "confidence", "数据不足"))
    if scope.kind == "season":
        if performance >= 25 and eligible:
            return "赛季强势"
        if performance >= 15 and eligible:
            return "赛季表现优秀"
        if performance >= 10 and eligible:
            return "赛季待验证"
        if performance <= -10 and eligible:
            return "赛季偏弱"
        return "赛季中性"
    if (
        performance >= 35
        and score >= 25
        and _confidence_at_least(confidence, "高")
        and getattr(hero, "effective_seasons", 0) >= 3
        and (getattr(hero, "stability", None) or 0) >= 60
    ):
        return "招牌绝活"
    if performance >= 25 and score >= 12 and _confidence_at_least(confidence, "中"):
        return "强势绝活"
    if performance >= 15 and eligible:
        return "潜力绝活"
    if performance >= 10 and eligible:
        return "待验证"
    if performance <= -10 and eligible:
        return "绝症候选"
    if performance <= -10:
        return "相对弱势"
    return "常用英雄"


def status_is_positive(status: str | None) -> bool:
    return str(status or "") in {
        "招牌绝活", "强势绝活", "潜力绝活", "待验证",
        "赛季强势", "赛季表现优秀", "赛季待验证",
    }


__all__ = [
    "ANALYSIS_MIN_COMPETITIVE_MATCHES",
    "ANALYSIS_MIN_QUICK_MATCHES",
    "ANALYSIS_MIN_TOTAL_MATCHES",
    "EVIDENCE_FACTORS",
    "PERSONAL_COMPETITIVE_PRIOR_MATCHES",
    "PERSONAL_QUICK_PRIOR_MATCHES",
    "PERFORMANCE_NEUTRAL_BAND",
    "adjust_personal_delta",
    "adjust_delta",
    "calculate_confidence",
    "calculate_evidence_factor",
    "calculate_performance_index",
    "calculate_performance_sickness_score",
    "calculate_play_index",
    "calculate_signature_score",
    "calculate_sickness_score",
    "calculate_stability",
    "classify_hero_performance",
    "is_analysis_eligible",
    "is_performance_sickness_candidate",
    "is_signature_candidate",
    "status_is_positive",
]
