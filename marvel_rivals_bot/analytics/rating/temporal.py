"""Temporal Rating Layer for Rating V2.

The temporal layer is deliberately additive.  Career values are calculated by
the existing engine and remain unchanged; this module only derives a second
view over the most recent half-seasons.  It consumes already-normalized,
per-season snapshots and therefore never performs network requests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from .combat import calculate_combat
from .confidence import calculate_confidence, shrink_performance
from .consistency import calculate_consistency
from .experience import calculate_experience
from .models import HeroRatingResult, RatingContext, RatingHeroSnapshot, SeasonRatingSnapshot
from .outcome import calculate_outcome
from .transforms import clamp, weighted_mean


RECENT_SEASON_WINDOW = 6
TEMPORAL_MIN_EFFECTIVE_MATCHES = 3.0
TEMPORAL_HALF_LIFE = 4.0
TEMPORAL_SAMPLE_SCALE = 15.0
TEMPORAL_OUTCOME_PRIOR_MATCHES = 20.0

TEMPORAL_STABLE = "\u7a33\u5b9a\u5f3a\u52bf"
TEMPORAL_RISING = "\u8fd1\u671f\u5d1b\u8d77"
TEMPORAL_FORMER = "\u66fe\u7ecf\u5f3a\u52bf"
TEMPORAL_DECLINING = "\u72b6\u6001\u56de\u843d"
TEMPORAL_VERIFY = "\u8fd1\u671f\u5f85\u9a8c\u8bc1"


@dataclass(frozen=True, slots=True)
class TemporalRating:
    """Derived values for one hero's current-time view."""

    freshness: float | None = None
    recent_outcome: float | None = None
    recent_combat: float | None = None
    recent_consistency: float | None = None
    recent_performance: float | None = None
    recent_mastery: float | None = None
    recent_specialization: float | None = None
    recent_confidence: float = 0.0
    trend: float | None = None
    temporal_label: str | None = None
    last_active_season: str | None = None
    recent_effective_matches: float = 0.0


def season_age(season_code: str | int, latest_season_code: str | int | None) -> int:
    """Return the number of half-seasons between two numeric CN seasons."""

    try:
        latest = int(latest_season_code) if latest_season_code is not None else int(season_code)
        return max(0, latest - int(season_code))
    except (TypeError, ValueError):
        return 0


def season_decay(age: int | float, *, half_life: float = TEMPORAL_HALF_LIFE) -> float:
    """Return the documented half-life decay weight."""

    return 2.0 ** (-max(0.0, float(age)) / max(0.0001, float(half_life)))


def _effective_matches(snapshot: SeasonRatingSnapshot) -> float:
    value = snapshot.competitive_effective_matches
    if value is None:
        value = (
            getattr(snapshot.competitive_stats, "effective_matches", None)
            if snapshot.competitive_stats is not None
            else None
        )
    if value is None:
        value = snapshot.competitive_matches
    return max(0.0, float(value or 0.0))


def _effective_wins(snapshot: SeasonRatingSnapshot) -> float | None:
    value = snapshot.competitive_effective_wins
    if value is None:
        value = (
            getattr(snapshot.competitive_stats, "effective_wins", None)
            if snapshot.competitive_stats is not None
            else None
        )
    if value is None:
        value = snapshot.competitive_wins
    return None if value is None else max(0.0, float(value))


def _latest_code(context: RatingContext, hero: RatingHeroSnapshot) -> str | None:
    if context.latest_season_code is not None:
        return str(context.latest_season_code)
    codes = [item.season_code for item in hero.season_snapshots]
    return max(codes, key=lambda value: int(value)) if codes else None


def _recent_snapshots(
    context: RatingContext,
    hero: RatingHeroSnapshot,
) -> tuple[tuple[SeasonRatingSnapshot, int, float], ...]:
    latest = _latest_code(context, hero)
    if latest is None:
        return ()
    rows = []
    for item in hero.season_snapshots:
        age = season_age(item.season_code, latest)
        if age >= RECENT_SEASON_WINDOW:
            continue
        matches = _effective_matches(item)
        if matches > 0:
            rows.append((item, age, season_decay(age)))
    return tuple(sorted(rows, key=lambda value: int(value[0].season_code)))


def calculate_freshness(
    snapshots: tuple[SeasonRatingSnapshot, ...] | list[SeasonRatingSnapshot],
    latest_season_code: str | int | None,
) -> tuple[float | None, str | None, float]:
    """Calculate Freshness, last valid season, and recent sample size.

    A season becomes evidence of current ability only after three effective
    competitive matches.  Smaller samples still contribute to the sample
    multiplier, preventing a single game from restoring a stale hero to 1.0.
    """

    latest = str(latest_season_code) if latest_season_code is not None else None
    if latest is None and snapshots:
        latest = max((item.season_code for item in snapshots), key=lambda value: int(value))
    if latest is None:
        return None, None, 0.0
    valid = [
        item for item in snapshots
        if season_age(item.season_code, latest) >= 0
        and _effective_matches(item) >= TEMPORAL_MIN_EFFECTIVE_MATCHES
    ]
    recent_sample = sum(
        _effective_matches(item)
        for item in snapshots
        if season_age(item.season_code, latest) < RECENT_SEASON_WINDOW
        and _effective_matches(item) > 0
    )
    if not valid:
        return 0.0, None, recent_sample
    last = max(valid, key=lambda item: int(item.season_code))
    age = season_age(last.season_code, latest)
    age_freshness = season_decay(age)
    sample_freshness = 1.0 - math.exp(-recent_sample / TEMPORAL_SAMPLE_SCALE)
    freshness = age_freshness * (0.35 + 0.65 * sample_freshness)
    return clamp(freshness, 0.0, 1.0), str(last.season_code), recent_sample


def _season_rows(hero: RatingHeroSnapshot, codes: set[str]) -> tuple[Any, ...]:
    return tuple(
        row for row in hero.seasons
        if str(getattr(row, "season_code", "")) in codes
    )


def _season_combat(
    context: RatingContext,
    hero: RatingHeroSnapshot,
    season_code: str,
) -> tuple[float | None, float]:
    season_context = context.season_contexts.get(str(season_code))
    if season_context is None:
        return None, 0.0
    current = next(
        (item for item in season_context.heroes if item.hero_id == hero.hero_id),
        None,
    )
    if current is None:
        return None, 0.0
    result = calculate_combat(season_context, current)
    return result.combat, result.observable_coverage


def calculate_temporal_rating(
    context: RatingContext,
    hero: RatingHeroSnapshot,
    career: HeroRatingResult,
) -> TemporalRating:
    """Calculate all temporal fields for one hero before peer specialization."""

    freshness, last_active, _recent_sample = calculate_freshness(
        hero.season_snapshots,
        _latest_code(context, hero),
    )
    recent = _recent_snapshots(context, hero)
    if not recent:
        return TemporalRating(
            freshness=freshness,
            last_active_season=last_active,
            trend=None,
        )

    weighted_matches = sum(weight * _effective_matches(item) for item, _age, weight in recent)
    weighted_wins = 0.0
    weighted_expected = 0.0
    outcome_weight = 0.0
    combat_values: list[tuple[float | None, float]] = []
    combat_coverage: list[tuple[float | None, float]] = []
    meta_coverage: list[tuple[float | None, float]] = []
    comparable_seasons = 0
    weighted_minutes_competitive = 0.0
    weighted_minutes_quick = 0.0
    weighted_quick_matches = 0.0

    for item, _age, weight in recent:
        matches = _effective_matches(item)
        wins = _effective_wins(item)
        meta_rate = item.meta_win_rate
        if wins is not None and meta_rate is not None:
            outcome_weight += weight * matches
            weighted_wins += weight * wins
            weighted_expected += weight * matches * float(meta_rate) / 100.0
            comparable_seasons += 1
            meta_coverage.append((100.0, weight * matches))
        else:
            meta_coverage.append((0.0, weight * matches))
        combat, coverage = _season_combat(context, hero, item.season_code)
        combat_values.append((combat, weight * matches))
        combat_coverage.append((coverage, weight * matches))
        comp_seconds = float(getattr(item.competitive_stats, "play_time", 0.0) or 0.0)
        quick_seconds = float(getattr(item.quick_stats, "play_time", 0.0) or 0.0)
        weighted_minutes_competitive += weight * comp_seconds / 60.0
        weighted_minutes_quick += weight * quick_seconds / 60.0
        weighted_quick_matches += weight * max(
            0.0,
            float(
                item.quick_effective_matches
                if item.quick_effective_matches is not None
                else getattr(item.quick_stats, "effective_matches", None)
                or getattr(item.quick_stats, "matches", None)
                or 0.0
            ),
        )

    recent_delta = None
    if outcome_weight > 0:
        recent_delta = (weighted_wins - weighted_expected) * 100.0 / outcome_weight
    if recent_delta is not None:
        recent_delta *= outcome_weight / (outcome_weight + TEMPORAL_OUTCOME_PRIOR_MATCHES)
    recent_outcome = calculate_outcome(recent_delta)

    recent_combat = weighted_mean(combat_values)
    recent_consistency = calculate_consistency(
        _season_rows(hero, {item.season_code for item, _age, _weight in recent}),
        latest_season_code=_latest_code(context, hero),
    )
    recent_meta_coverage = weighted_mean(meta_coverage) or 0.0
    recent_observable_coverage = weighted_mean(combat_coverage) or 0.0
    recent_confidence, _components = calculate_confidence(
        weighted_matches,
        recent_meta_coverage,
        recent_observable_coverage,
        comparable_seasons,
    )
    raw = weighted_mean(
        (
            (recent_outcome, 0.50),
            (recent_combat, 0.35),
            (recent_consistency, 0.15),
        )
    )
    recent_performance = None if raw is None else shrink_performance(raw, recent_confidence)
    active_seasons = sum(1 for item, _age, _weight in recent if _effective_matches(item) > 0)
    recent_experience = calculate_experience(
        weighted_matches,
        weighted_minutes_competitive,
        weighted_quick_matches,
        weighted_minutes_quick,
        active_seasons,
    )
    recent_mastery = (
        0.75 * recent_performance + 0.25 * recent_experience
        if recent_performance is not None
        else None
    )
    trend = (
        recent_performance - career.performance
        if recent_performance is not None and career.performance is not None
        else None
    )
    return TemporalRating(
        freshness=freshness,
        recent_outcome=recent_outcome,
        recent_combat=recent_combat,
        recent_consistency=recent_consistency,
        recent_performance=recent_performance,
        recent_mastery=recent_mastery,
        recent_confidence=recent_confidence,
        trend=trend,
        last_active_season=last_active,
        recent_effective_matches=weighted_matches,
    )


def _career_strong(result: HeroRatingResult) -> bool:
    return (
        result.classification in {"\u62db\u724c\u7edd\u6d3b", "\u5f3a\u52bf\u7edd\u6d3b", "\u6f5c\u529b\u7edd\u6d3b"}
        or (
            result.mastery >= 78.0
            and result.confidence >= 0.70
            and (result.specialization is None or result.specialization >= 10.0)
        )
    )


def _recent_strong(result: HeroRatingResult) -> bool:
    return (
        result.recent_performance is not None
        and result.recent_mastery is not None
        and result.recent_performance >= 78.0
        and result.recent_mastery >= 78.0
        and result.recent_confidence >= 0.70
        and (
            result.recent_specialization is None
            or result.recent_specialization >= 10.0
        )
    )


def classify_temporal_state(result: HeroRatingResult) -> str:
    """Return an independent current-time label without changing Career fields."""

    freshness = result.freshness
    recent = result.recent_performance
    if recent is None or result.recent_effective_matches < TEMPORAL_MIN_EFFECTIVE_MATCHES:
        return TEMPORAL_VERIFY
    if _career_strong(result) and freshness is not None and freshness < 0.45:
        return TEMPORAL_FORMER
    if (
        _career_strong(result)
        and freshness is not None
        and freshness >= 0.65
        and recent <= result.performance - 8.0
    ):
        return TEMPORAL_DECLINING
    if (
        _recent_strong(result)
        and freshness is not None
        and freshness >= 0.70
        and recent >= result.performance + 8.0
    ):
        return TEMPORAL_RISING
    if _career_strong(result) and _recent_strong(result) and (freshness or 0.0) >= 0.70:
        return TEMPORAL_STABLE
    if freshness is not None and 0.45 <= freshness < 0.70:
        return TEMPORAL_VERIFY
    if _recent_strong(result) and freshness is not None and freshness >= 0.70:
        return TEMPORAL_RISING
    return TEMPORAL_VERIFY


def apply_temporal_ratings(
    results: dict[str, HeroRatingResult],
    context: RatingContext,
) -> dict[str, HeroRatingResult]:
    """Attach temporal values and recent leave-one-out specialization."""

    temporal = {
        hero_id: calculate_temporal_rating(
            context,
            hero,
            results[hero_id],
        )
        for hero_id, hero in ((item.hero_id, item) for item in context.heroes)
        if hero_id in results
    }
    with_base = {
        hero_id: replace(
            results[hero_id],
            freshness=value.freshness,
            recent_outcome=value.recent_outcome,
            recent_combat=value.recent_combat,
            recent_consistency=value.recent_consistency,
            recent_performance=value.recent_performance,
            recent_mastery=value.recent_mastery,
            recent_confidence=value.recent_confidence,
            trend=value.trend,
            last_active_season=value.last_active_season,
            recent_effective_matches=value.recent_effective_matches,
        )
        for hero_id, value in temporal.items()
    }
    for hero_id, result in tuple(with_base.items()):
        peers = [
            item for key, item in with_base.items()
            if key != hero_id
            and item.recent_performance is not None
            and item.recent_effective_matches >= TEMPORAL_MIN_EFFECTIVE_MATCHES
        ]
        if len(peers) >= 3 and result.recent_performance is not None:
            weighted = [
                (
                    item.recent_performance,
                    max(0.01, item.recent_confidence)
                    * max(0.01, float(item.recent_mastery or 0.0) / 100.0),
                )
                for item in peers
            ]
            baseline = weighted_mean(weighted)
            recent_spec = None if baseline is None else result.recent_performance - baseline
            result = replace(result, recent_specialization=recent_spec)
        with_base[hero_id] = replace(result, temporal_label=classify_temporal_state(result))
    return with_base


__all__ = [
    "RECENT_SEASON_WINDOW",
    "TEMPORAL_MIN_EFFECTIVE_MATCHES",
    "TEMPORAL_HALF_LIFE",
    "TemporalRating",
    "calculate_freshness",
    "calculate_temporal_rating",
    "classify_temporal_state",
    "apply_temporal_ratings",
    "season_age",
    "season_decay",
]
