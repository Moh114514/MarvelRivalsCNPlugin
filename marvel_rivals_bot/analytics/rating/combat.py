"""Role-aware robust combat scoring."""

from __future__ import annotations

from dataclasses import dataclass, field

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
    baseline_peer_count: int = 0
    baseline_quality: float = 0.0
    peer_quality: float = 0.0
    final_quality: float = 0.0
    raw_dimension_score: dict[str, float | None] = field(default_factory=dict)
    shrunk_dimension_score: dict[str, float | None] = field(default_factory=dict)


_BASELINE_QUALITY = {
    "同 MetricProfile": 1.0,
    "同职责 + 同 TacticalFunction": 0.85,
    "同 OfficialRole": 0.6,
}
_PEER_QUALITY_FULL_COUNT = 5


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


def _peer_quality(peer_count: int) -> float:
    """Return a bounded quality factor for the size of the peer sample.

    Baselines require three peers, while five peers are treated as a full
    sample.  This keeps the existing eligibility/fallback rules intact and
    makes the amount of peer evidence visible to calibration diagnostics.
    """

    return min(1.0, max(0.0, float(peer_count) / _PEER_QUALITY_FULL_COUNT))


def calculate_combat(context: RatingContext, current: RatingHeroSnapshot) -> CombatResult:
    peers, group_name = _group(context, current)
    if not peers:
        unavailable = {dimension.value: None for dimension in MetricDimension}
        return CombatResult(
            None,
            unavailable,
            0.0,
            None,
            raw_dimension_score=dict(unavailable),
            shrunk_dimension_score=dict(unavailable),
        )
    raw_dimensions: dict[str, float | None] = {}
    for dimension in (MetricDimension.FIN, MetricDimension.PRS, MetricDimension.SUR, MetricDimension.TEAM, MetricDimension.HEAL, MetricDimension.FRONT, MetricDimension.UTIL):
        if dimension is MetricDimension.FRONT:
            current_taken = _value(current, MetricDimension.FRONT)
            current_survival = _value(current, MetricDimension.SUR)
            peer_taken = [value for value in (_value(item, MetricDimension.FRONT) for item in peers) if value is not None]
            peer_survival = [value for value in (_value(item, MetricDimension.SUR) for item in peers) if value is not None]
            if current_taken is None or current_survival is None or not peer_taken or not peer_survival:
                raw_dimensions[dimension.value] = None
            else:
                raw_dimensions[dimension.value] = 0.65 * robust_score(current_taken, peer_taken, max_z=2.0) + 0.35 * robust_score(current_survival, peer_survival)
            continue
        current_value = _value(current, dimension)
        peer_values = [value for value in (_value(item, dimension) for item in peers) if value is not None]
        if current_value is None or not peer_values:
            raw_dimensions[dimension.value] = None
            continue
        raw_dimensions[dimension.value] = robust_score(current_value, peer_values, max_z=2.0 if dimension is MetricDimension.FRONT else 3.0)
    profile = METRIC_PROFILES[current.archetype.metric_profile]
    baseline_quality = _BASELINE_QUALITY.get(group_name or "", 0.0)
    peer_quality = _peer_quality(len(peers))
    final_quality = baseline_quality * peer_quality
    shrunk_dimensions = {
        key: None if value is None else 50.0 + final_quality * (value - 50.0)
        for key, value in raw_dimensions.items()
    }
    available = [(shrunk_dimensions[dimension.value], weight) for dimension, weight in profile.weights]
    combat = weighted_mean(available)
    coverage = 100.0 * sum(weight for value, weight in available if value is not None) / profile.total_weight
    return CombatResult(
        combat,
        shrunk_dimensions,
        coverage,
        group_name,
        baseline_peer_count=len(peers),
        baseline_quality=baseline_quality,
        peer_quality=peer_quality,
        final_quality=final_quality,
        raw_dimension_score=raw_dimensions,
        shrunk_dimension_score=shrunk_dimensions,
    )


__all__ = ["CombatResult", "calculate_combat"]
