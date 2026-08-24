"""Role-aware robust combat scoring."""

from __future__ import annotations

from dataclasses import dataclass

from ..archetypes import MetricDimension
from ..archetypes.profiles import METRIC_PROFILES
from ...reference.heroes import HERO_ROLE_MAP
from ..models import NormalizedModeStats
from .models import RatingContext, RatingHeroSnapshot
from .transforms import robust_score, weighted_mean


@dataclass(frozen=True, slots=True)
class CombatResult:
    combat: float | None
    dimensions: dict[str, float | None]
    observable_coverage: float
    baseline_group: str | None


def _value(snapshot: RatingHeroSnapshot, dimension: MetricDimension) -> float | None:
    stats: NormalizedModeStats = snapshot.competitive_stats
    if dimension is MetricDimension.FIN:
        return _mean_nonempty((stats.per10_final_hits, 0.65), (stats.per10_kills, 0.35))
    if dimension is MetricDimension.PRS:
        return _number(stats.per10_hero_damage)
    if dimension is MetricDimension.SUR:
        deaths = stats.per10_deaths
        return -deaths if deaths is not None else None
    if dimension is MetricDimension.TEAM:
        return _number(stats.per10_assists)
    if dimension is MetricDimension.HEAL:
        return _number(stats.per10_heal)
    if dimension is MetricDimension.FRONT:
        return _number(stats.per10_damage_taken)
    # UTIL and MECH intentionally stay unavailable until a dynamic feature is
    # explicitly validated and enabled for rating.
    return None


def _number(value):
    return None if value is None else float(value)


def _mean_nonempty(*pairs):
    values = [(value, weight) for value, weight in pairs if value is not None]
    return weighted_mean(values)


def _group(context: RatingContext, current: RatingHeroSnapshot) -> tuple[list[RatingHeroSnapshot], str | None]:
    def official_role(item: RatingHeroSnapshot):
        try:
            return HERO_ROLE_MAP.get(int(item.hero_id))
        except (TypeError, ValueError):
            return None

    current_role = official_role(current)
    eligible = [
        item for item in context.heroes
        if item.hero_id != current.hero_id
        and (
            item.competitive_effective_matches
            if item.competitive_effective_matches is not None
            else item.competitive_matches
        ) >= 5
    ]
    checks = (
        (lambda item: item.archetype.metric_profile == current.archetype.metric_profile, "同 MetricProfile"),
        (
            lambda item: current_role is not None
            and official_role(item) == current_role
            and item.archetype.function == current.archetype.function,
            "同职责 + 同 TacticalFunction",
        ),
    )
    for predicate, label in checks:
        candidates = [item for item in eligible if predicate(item)]
        if len(candidates) >= 3:
            return candidates, label
    # Official role is deliberately read from the archetype's tactical data;
    # the archetype validation guarantees it was authored against the official
    # role map.  This fallback remains deterministic when no role peer exists.
    candidates = [
        item for item in eligible
        if current_role is not None and official_role(item) == current_role
    ]
    if len(candidates) >= 3:
        return candidates, "同 OfficialRole"
    return [], None


def calculate_combat(context: RatingContext, current: RatingHeroSnapshot) -> CombatResult:
    peers, group_name = _group(context, current)
    if not peers:
        return CombatResult(None, {dimension.value: None for dimension in MetricDimension}, 0.0, None)
    dimensions: dict[str, float | None] = {}
    for dimension in (MetricDimension.FIN, MetricDimension.PRS, MetricDimension.SUR, MetricDimension.TEAM, MetricDimension.HEAL, MetricDimension.FRONT, MetricDimension.UTIL):
        if dimension is MetricDimension.FRONT:
            current_taken = _value(current, MetricDimension.FRONT)
            current_survival = _value(current, MetricDimension.SUR)
            peer_taken = [value for value in (_value(item, MetricDimension.FRONT) for item in peers) if value is not None]
            peer_survival = [value for value in (_value(item, MetricDimension.SUR) for item in peers) if value is not None]
            if current_taken is None or current_survival is None or not peer_taken or not peer_survival:
                dimensions[dimension.value] = None
            else:
                dimensions[dimension.value] = 0.65 * robust_score(current_taken, peer_taken, max_z=2.0) + 0.35 * robust_score(current_survival, peer_survival)
            continue
        current_value = _value(current, dimension)
        peer_values = [value for value in (_value(item, dimension) for item in peers) if value is not None]
        if current_value is None or not peer_values:
            dimensions[dimension.value] = None
            continue
        dimensions[dimension.value] = robust_score(current_value, peer_values, max_z=2.0 if dimension is MetricDimension.FRONT else 3.0)
    profile = METRIC_PROFILES[current.archetype.metric_profile]
    available = [(dimensions[dimension.value], weight) for dimension, weight in profile.weights]
    combat = weighted_mean(available)
    coverage = 100.0 * sum(weight for value, weight in available if value is not None) / profile.total_weight
    return CombatResult(combat, dimensions, coverage, group_name)


__all__ = ["CombatResult", "calculate_combat"]
