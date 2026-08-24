"""Rating V2 orchestration: pure calculations only."""

from __future__ import annotations

from dataclasses import replace

from .combat import calculate_combat
from .confidence import calculate_confidence, shrink_performance
from .consistency import calculate_consistency
from .experience import calculate_experience
from .models import HeroRatingResult, RatingContext, RatingHeroSnapshot
from .outcome import calculate_outcome
from .specialization import apply_specialization, classify_rating
from .transforms import weighted_mean


class HeroRatingEngine:
    version = "v2"

    def rate(self, context: RatingContext, hero: RatingHeroSnapshot) -> HeroRatingResult:
        outcome = calculate_outcome(hero.outcome_delta)
        combat_result = calculate_combat(context, hero)
        consistency = calculate_consistency(hero.seasons, latest_season_code=context.latest_season_code)
        experience = calculate_experience(
            hero.competitive_matches,
            hero.competitive_stats.play_time / 60 if hero.competitive_stats.play_time else None,
            hero.quick_stats.matches,
            hero.quick_stats.play_time / 60 if hero.quick_stats.play_time else None,
            hero.active_seasons,
        )
        confidence, components = calculate_confidence(
            hero.competitive_matches,
            hero.meta_coverage,
            combat_result.observable_coverage,
            hero.comparable_seasons,
        )
        raw = weighted_mean(((outcome, 0.50), (combat_result.combat, 0.35), (consistency, 0.15)))
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
            mastery=0.75 * performance + 0.25 * experience,
            dimensions=combat_result.dimensions,
            confidence_components=components,
            observable_coverage=combat_result.observable_coverage,
            baseline_group=combat_result.baseline_group,
        )
        return result

    def rate_many(self, context: RatingContext) -> dict[str, HeroRatingResult]:
        results = {hero.hero_id: self.rate(context, hero) for hero in context.heroes}
        results = apply_specialization(results)
        return {hero_id: replace(result, classification=classify_rating(result)) for hero_id, result in results.items()}


__all__ = ["HeroRatingEngine"]
