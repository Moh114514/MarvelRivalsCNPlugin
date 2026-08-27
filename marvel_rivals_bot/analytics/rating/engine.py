"""Rating V2 orchestration: pure calculations only."""

from __future__ import annotations

from dataclasses import replace

from .combat import calculate_combat
from .confidence import calculate_confidence, shrink_performance
from .consistency import calculate_consistency
from .constants import (
    RATING_V2_COMBAT_WEIGHT,
    RATING_V2_CONSISTENCY_WEIGHT,
    RATING_V2_MASTERY_EXPERIENCE_WEIGHT,
    RATING_V2_MASTERY_PERFORMANCE_WEIGHT,
    RATING_V2_OUTCOME_WEIGHT,
)
from .experience import calculate_experience
from .models import HeroRatingResult, RatingContext, RatingHeroSnapshot
from .outcome import calculate_outcome
from .specialization import (
    SpecializationEvidencePolicy,
    apply_specialization,
    classify_rating,
)
from .temporal import apply_temporal_ratings, calculate_temporal_rating, classify_temporal_state
from .transforms import weighted_mean


class HeroRatingEngine:
    version = "v2"

    def __init__(self, *, specialization_evidence_policy: SpecializationEvidencePolicy | None = None) -> None:
        self.specialization_evidence_policy = specialization_evidence_policy or SpecializationEvidencePolicy()

    def rate(self, context: RatingContext, hero: RatingHeroSnapshot) -> HeroRatingResult:
        competitive_matches = (
            hero.competitive_effective_matches
            if hero.competitive_effective_matches is not None
            else hero.competitive_matches
        )
        quick_matches = (
            hero.quick_effective_matches
            if hero.quick_effective_matches is not None
            else (
                hero.quick_stats.effective_matches
                if hero.quick_stats.effective_matches is not None
                else hero.quick_stats.matches
            )
        )
        outcome = calculate_outcome(hero.outcome_delta)
        combat_result = calculate_combat(context, hero)
        consistency = calculate_consistency(hero.seasons, latest_season_code=context.latest_season_code)
        experience = calculate_experience(
            competitive_matches,
            hero.competitive_stats.play_time / 60 if hero.competitive_stats.play_time else None,
            quick_matches,
            hero.quick_stats.play_time / 60 if hero.quick_stats.play_time else None,
            hero.active_seasons,
        )
        confidence, components = calculate_confidence(
            competitive_matches,
            hero.meta_coverage,
            combat_result.observable_coverage,
            hero.comparable_seasons,
        )
        raw = weighted_mean(((outcome, RATING_V2_OUTCOME_WEIGHT), (combat_result.combat, RATING_V2_COMBAT_WEIGHT), (consistency, RATING_V2_CONSISTENCY_WEIGHT)))
        raw = 50.0 if raw is None else raw
        performance = shrink_performance(raw, confidence)
        result = HeroRatingResult(
            hero_id=hero.hero_id,
            hero_name=hero.hero_name,
            archetype=hero.archetype,
            outcome=outcome,
            combat=combat_result.combat,
            consistency=consistency,
            experience=experience,
            performance_raw=raw,
            performance=performance,
            confidence=confidence,
            mastery=(
                RATING_V2_MASTERY_PERFORMANCE_WEIGHT * performance
                + RATING_V2_MASTERY_EXPERIENCE_WEIGHT * experience
            ),
            dimensions=combat_result.dimensions,
            confidence_components=components,
            observable_coverage=combat_result.observable_coverage,
            baseline_group=combat_result.baseline_group,
            baseline_peer_count=combat_result.baseline_peer_count,
            baseline_quality=combat_result.baseline_quality,
            peer_quality=combat_result.peer_quality,
            final_quality=combat_result.final_quality,
            raw_dimension_score=combat_result.raw_dimension_score,
            shrunk_dimension_score=combat_result.shrunk_dimension_score,
        )
        temporal = (
            calculate_temporal_rating(context, hero, result)
            if context.scope == "career"
            else None
        )
        if temporal is None:
            return result
        result = replace(
            result,
            freshness=temporal.freshness,
            recent_outcome=temporal.recent_outcome,
            recent_combat=temporal.recent_combat,
            recent_consistency=temporal.recent_consistency,
            recent_performance=temporal.recent_performance,
            recent_mastery=temporal.recent_mastery,
            recent_confidence=temporal.recent_confidence,
            trend=temporal.trend,
            temporal_label=temporal.temporal_label,
            last_active_season=temporal.last_active_season,
            recent_effective_matches=temporal.recent_effective_matches,
        )
        return replace(result, temporal_label=classify_temporal_state(result))

    def rate_many(self, context: RatingContext) -> dict[str, HeroRatingResult]:
        results = {hero.hero_id: self.rate(context, hero) for hero in context.heroes}
        results = apply_specialization(results, evidence_policy=self.specialization_evidence_policy)
        if context.scope == "career":
            results = apply_temporal_ratings(results, context)
        return {
            hero_id: replace(result, classification=classify_rating(result, scope=context.scope))
            for hero_id, result in results.items()
        }


__all__ = ["HeroRatingEngine"]
