"""Pure, transparent rules for cross-season specialty analysis."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


SIGNATURE_PRIOR_MATCHES = 20
SIGNATURE_STABILITY_MIN_MATCHES = 1

SICKNESS_MIN_TOTAL_MATCHES = 10
SICKNESS_MIN_COMPETITIVE_MATCHES = 5
SICKNESS_MIN_QUICK_MATCHES = 20
SICKNESS_META_PROTECTION_DELTA = 2.0

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
) -> float:
    """Return how much a player keeps returning to a hero, on a 0-100 scale.

    Competitive volume has 40% weight, Quick volume 20%, and the hero's
    share of all games 40%. Each signal saturates instead of growing without
    bound, so one very large number cannot dominate the whole ranking.
    """

    competitive = _score_from_cap(competitive_matches, 50) or 0.0
    quick = _score_from_cap(quick_matches, 50) or 0.0
    share = _score_from_cap(usage_share, 20) or 0.0
    return round(competitive * 0.40 + quick * 0.20 + share * 0.40, 4)


def calculate_weakness_index(
    meta_disadvantage: float | None,
    personal_competitive_disadvantage: float | None,
    personal_quick_disadvantage: float | None,
) -> float:
    """Combine available below-baseline signals into a 0-100 score.

    Meta, personal Competitive, and personal Quick disadvantages are capped
    at 8pp, 8pp, and 10pp respectively. Missing signals are omitted and the
    remaining weights are renormalized, so partial history is still useful.
    """

    signals = (
        (meta_disadvantage, 8.0, 0.55),
        (personal_competitive_disadvantage, 8.0, 0.30),
        (personal_quick_disadvantage, 10.0, 0.15),
    )
    weighted = 0.0
    weight_total = 0.0
    for value, cap, weight in signals:
        normalized = _score_from_cap(value, cap)
        if normalized is None:
            continue
        weighted += normalized * weight
        weight_total += weight
    if weight_total == 0:
        return 0.0
    return round(weighted / weight_total, 4)


def is_sickness_candidate(
    *,
    total_matches: int,
    competitive_matches: int,
    quick_matches: int,
    has_win_rate: bool,
    adjusted_delta: float | None,
    comparable_matches: int,
) -> bool:
    """Apply the soft volume floor and protect obvious Meta-relative stars."""

    total = max(0, int(total_matches or 0))
    competitive = max(0, int(competitive_matches or 0))
    quick = max(0, int(quick_matches or 0))
    if not has_win_rate:
        return False
    if not (
        total >= SICKNESS_MIN_TOTAL_MATCHES
        or competitive >= SICKNESS_MIN_COMPETITIVE_MATCHES
        or quick >= SICKNESS_MIN_QUICK_MATCHES
    ):
        return False
    if (
        adjusted_delta is not None
        and int(comparable_matches or 0) >= 20
        and float(adjusted_delta) >= SICKNESS_META_PROTECTION_DELTA
    ):
        return False
    return True


def calculate_sick_score(
    *,
    play_index: float,
    weakness_index: float,
    total_matches: int,
    competitive_matches: int,
    quick_matches: int,
    has_win_rate: bool,
    adjusted_delta: float | None,
    comparable_matches: int,
) -> float:
    """Return the entertainment-oriented sickness index.

    This is intentionally a relative ranking score rather than a diagnosis:
    ``play_index * weakness_index / 100``.
    """

    if not is_sickness_candidate(
        total_matches=total_matches,
        competitive_matches=competitive_matches,
        quick_matches=quick_matches,
        has_win_rate=has_win_rate,
        adjusted_delta=adjusted_delta,
        comparable_matches=comparable_matches,
    ):
        return 0.0
    try:
        return round(max(0.0, float(play_index)) * max(0.0, float(weakness_index)) / 100, 4)
    except (TypeError, ValueError):
        return 0.0


def sickness_severity(score: float | None) -> str:
    """Translate the continuous score into a plain-language display label."""

    value = max(0.0, float(score or 0.0))
    if value >= 70:
        return "重度"
    if value >= 40:
        return "明显"
    if value >= 15:
        return "轻微"
    if value > 0:
        return "疑似"
    return "暂无"


def sick_hero_sort_key(item: Any) -> tuple[float, float, float, int, float]:
    """Sort by sickness index, then repeated use and weakness evidence."""

    return (
        -float(getattr(item, "sick_score", 0.0) or 0.0),
        -float(getattr(item, "play_index", 0.0) or 0.0),
        -float(getattr(item, "weakness_index", 0.0) or 0.0),
        -int(getattr(item, "total_matches", 0) or 0),
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
    "SICKNESS_MIN_COMPETITIVE_MATCHES",
    "SICKNESS_MIN_QUICK_MATCHES",
    "SICKNESS_MIN_TOTAL_MATCHES",
    "SICKNESS_META_PROTECTION_DELTA",
    "adjust_delta",
    "build_signature_tags",
    "calculate_confidence",
    "calculate_play_index",
    "calculate_sick_score",
    "calculate_weakness_index",
    "calculate_stability",
    "classify_signature",
    "classification_sort_key",
    "is_sickness_candidate",
    "sick_hero_sort_key",
    "sickness_severity",
    "stability_counts",
]
