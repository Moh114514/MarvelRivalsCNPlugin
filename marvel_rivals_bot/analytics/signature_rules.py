"""Pure, transparent rules for cross-season specialty analysis."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


SIGNATURE_PRIOR_MATCHES = 20
SIGNATURE_STABILITY_MIN_MATCHES = 1

CLASSIFICATION_ORDER = {
    "招牌绝活": 0,
    "强势绝活": 1,
    "潜力绝活": 2,
    "待验证": 3,
    "常用英雄": 4,
}


def adjust_delta(
    raw_delta: float | None,
    comparable_matches: int,
    prior_matches: int = SIGNATURE_PRIOR_MATCHES,
) -> float | None:
    """Shrink a percentage-point delta toward zero for small samples."""

    if raw_delta is None:
        return None
    try:
        matches = max(0, int(comparable_matches))
        prior = max(0, int(prior_matches))
    except (TypeError, ValueError):
        return None
    if matches == 0:
        return 0.0
    return float(raw_delta) * matches / (matches + prior)


def stability_counts(
    seasons: Iterable[Any],
    min_competitive_matches: int = SIGNATURE_STABILITY_MIN_MATCHES,
) -> tuple[float | None, int, int]:
    """Return weighted stability, effective season count and positive count.

    Any season with at least one competitive game is effective. Stability
    only uses seasons with a same-season Meta comparison, weighted by
    competitive games and capped at 20 games per season.
    """

    effective = 0
    positive = 0
    total_weight = 0
    positive_weight = 0
    for season in seasons:
        matches = getattr(season, "competitive_matches", None)
        delta = getattr(season, "raw_delta", None)
        if matches is None or int(matches) < min_competitive_matches:
            continue
        effective += 1
        if delta is None:
            continue
        weight = min(int(matches), 20)
        if weight <= 0:
            continue
        total_weight += weight
        if float(delta) > 0:
            positive += 1
            positive_weight += weight
    if total_weight == 0:
        return None, effective, positive
    return positive_weight * 100 / total_weight, effective, positive


def calculate_sick_score(
    actual_win_rate: float | None,
    competitive_matches: int,
    baseline_win_rate: float | None,
) -> float:
    """Score high-exposure heroes whose win rate trails the player's baseline."""

    if actual_win_rate is None or baseline_win_rate is None:
        return 0.0
    matches = max(0, int(competitive_matches))
    deficit = max(0.0, float(baseline_win_rate) - float(actual_win_rate))
    return deficit * matches


def sick_hero_sort_key(item: Any) -> tuple[float, int, float]:
    """Sort the most costly high-volume, below-baseline heroes first."""

    return (
        -float(getattr(item, "sick_score", 0.0) or 0.0),
        -int(getattr(item, "competitive_matches", 0) or 0),
        float(getattr(item, "actual_win_rate", 100.0) or 100.0),
    )


def calculate_stability(
    seasons: Iterable[Any],
    min_competitive_matches: int = SIGNATURE_STABILITY_MIN_MATCHES,
) -> float | None:
    """Calculate weighted positive-season stability as a percentage."""

    return stability_counts(seasons, min_competitive_matches)[0]


def calculate_confidence(
    comparable_matches: int,
    meta_coverage: float,
    rank_specific_coverage: float,
) -> str:
    """Classify evidence quality and downgrade incomplete Meta coverage."""

    matches = max(0, int(comparable_matches))
    if matches < 5:
        level = 0  # 数据不足
    elif matches < 20:
        level = 1  # 低
    elif matches < 50:
        level = 2  # 中
    elif matches < 100:
        level = 3  # 高
    else:
        level = 4  # 很高
    if float(meta_coverage) < 70 or float(rank_specific_coverage) < 70:
        level = max(0, level - 1)
    return ("数据不足", "低", "中", "高", "很高")[level]


def classify_signature(
    *,
    competitive_matches: int,
    effective_seasons: int,
    raw_delta: float | None,
    adjusted_delta: float | None,
    stability: float | None,
    meta_coverage: float,
) -> str:
    """Apply the V1 transparent classification thresholds."""

    raw = float(raw_delta) if raw_delta is not None else float("-inf")
    adjusted = float(adjusted_delta) if adjusted_delta is not None else float("-inf")
    stable = float(stability) if stability is not None else float("-inf")
    matches = int(competitive_matches)
    coverage = float(meta_coverage)
    if (
        matches >= 50
        and effective_seasons >= 3
        and adjusted >= 3.0
        and stable >= 65
        and coverage >= 70
    ):
        return "招牌绝活"
    if (
        matches >= 20
        and adjusted >= 2.0
        and coverage >= 60
        and (effective_seasons < 2 or stable >= 50)
    ):
        return "强势绝活"
    if (
        5 <= matches < 20
        and raw >= 5.0
        and adjusted >= 1.5
        and coverage >= 50
    ):
        return "潜力绝活"
    if matches < 5 and raw > 0:
        return "待验证"
    return "常用英雄"


def build_signature_tags(
    *,
    seasons: Iterable[Any],
    active_seasons: int,
    competitive_matches: int,
    effective_seasons: int,
    stability: float | None,
    adjusted_delta: float | None,
    expected_meta_win_rate: float | None,
    total_matches: int,
    is_favorite: bool = False,
) -> tuple[str, ...]:
    """Build descriptive tags that remain independent of the skill class."""

    tags: list[str] = []
    stable = stability is not None and stability >= 75
    delta = adjusted_delta is not None
    if effective_seasons >= 3 and stable and delta and adjusted_delta >= 2:
        tags.append("常青绝活")
    if active_seasons >= 5 and competitive_matches >= 50:
        tags.append("长期专精")

    season_list = list(seasons)
    recent = season_list[-2:]
    recent_total = sum(max(0, int(getattr(item, "competitive_matches", 0) or 0)) for item in recent)
    if competitive_matches > 0 and recent_total / competitive_matches >= 0.60 and recent:
        recent_deltas = [getattr(item, "raw_delta", None) for item in recent]
        if any(value is not None and float(value) > 0 for value in recent_deltas):
            tags.append("新晋绝活")
    if (
        expected_meta_win_rate is not None
        and expected_meta_win_rate < 49
        and adjusted_delta is not None
        and adjusted_delta >= 4
    ):
        tags.append("逆版本绝活")
    if is_favorite or (total_matches >= 30 and total_matches > 0):
        # The caller marks the actual favorite. The fallback condition keeps
        # this helper useful in isolation without making every small sample a
        # preference tag.
        if is_favorite:
            tags.append("本命英雄")
    return tuple(tags)


def classification_sort_key(item: Any) -> tuple[Any, ...]:
    """Stable ranking key used after all calculations are complete."""

    classification = getattr(item, "classification", "常用英雄")
    return (
        CLASSIFICATION_ORDER.get(classification, len(CLASSIFICATION_ORDER)),
        -(float("-inf") if getattr(item, "adjusted_delta", None) is None else float(getattr(item, "adjusted_delta"))),
        -int(getattr(item, "comparable_matches", 0) or 0),
        -(float("-inf") if getattr(item, "stability", None) is None else float(getattr(item, "stability"))),
        -int(getattr(item, "total_matches", 0) or 0),
    )


__all__ = [
    "CLASSIFICATION_ORDER",
    "SIGNATURE_PRIOR_MATCHES",
    "SIGNATURE_STABILITY_MIN_MATCHES",
    "adjust_delta",
    "build_signature_tags",
    "calculate_confidence",
    "calculate_sick_score",
    "calculate_stability",
    "classify_signature",
    "classification_sort_key",
    "sick_hero_sort_key",
    "stability_counts",
]
