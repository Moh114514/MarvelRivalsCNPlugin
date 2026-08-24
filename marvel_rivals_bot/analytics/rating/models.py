"""Input/output models for the pure Rating V2 engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from ..archetypes import HeroArchetype, get_archetype

if TYPE_CHECKING:
    from ..models import HeroSeasonPerformance, NormalizedModeStats


@dataclass(frozen=True, slots=True)
class RatingHeroSnapshot:
    hero_id: str
    hero_name: str
    archetype: HeroArchetype
    competitive_stats: "NormalizedModeStats"
    quick_stats: "NormalizedModeStats"
    competitive_matches: int
    outcome_delta: float | None
    meta_coverage: float
    seasons: tuple["HeroSeasonPerformance", ...] = ()
    comparable_seasons: int = 0
    active_seasons: int = 0
    competitive_effective_matches: float | None = None
    competitive_effective_wins: float | None = None
    quick_effective_matches: float | None = None


@dataclass(frozen=True, slots=True)
class RatingContext:
    heroes: tuple[RatingHeroSnapshot, ...]
    latest_season_code: str | None = None
    scope: str = "career"


@dataclass(frozen=True, slots=True)
class HeroRatingResult:
    """Stable V2 result consumed by text and HTML presentation layers."""

    hero_id: str
    hero_name: str
    archetype: HeroArchetype
    outcome: float | None
    combat: float | None
    consistency: float | None
    experience: float
    performance_raw: float
    performance: float
    confidence: float
    mastery: float
    specialization: float | None = None
    classification: str = "常用英雄"
    dimensions: dict[str, float | None] = field(default_factory=dict)
    confidence_components: dict[str, float] = field(default_factory=dict)
    observable_coverage: float = 0.0
    baseline_group: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "hero_id": self.hero_id,
            "hero_name": self.hero_name,
            "archetype": {
                "hero_id": self.archetype.hero_id,
                "primary_style": self.archetype.primary_style.value,
                "secondary_style": self.archetype.secondary_style.value if self.archetype.secondary_style else None,
                "function": self.archetype.function.value,
                "metric_profile": self.archetype.metric_profile.value,
                "tags": list(self.archetype.tags),
            },
            "outcome": self.outcome,
            "combat": self.combat,
            "consistency": self.consistency,
            "experience": self.experience,
            "performance_raw": self.performance_raw,
            "performance": self.performance,
            "confidence": self.confidence,
            "mastery": self.mastery,
            "specialization": self.specialization,
            "classification": self.classification,
            "dimensions": dict(self.dimensions),
            "confidence_components": dict(self.confidence_components),
            "observable_coverage": self.observable_coverage,
            "baseline_group": self.baseline_group,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HeroRatingResult":
        archetype_value = value.get("archetype")
        hero_id = str(value.get("hero_id", ""))
        archetype = get_archetype(int(archetype_value.get("hero_id", hero_id))) if isinstance(archetype_value, dict) else get_archetype(int(hero_id))
        if archetype is None:
            raise ValueError(f"unknown hero archetype: {hero_id}")
        return cls(
            hero_id=hero_id,
            hero_name=str(value.get("hero_name", "未知英雄")),
            archetype=archetype,
            outcome=_float(value.get("outcome")),
            combat=_float(value.get("combat")),
            consistency=_float(value.get("consistency")),
            experience=float(value.get("experience", 0.0) or 0.0),
            performance_raw=float(value.get("performance_raw", 50.0) or 50.0),
            performance=float(value.get("performance", 50.0) or 50.0),
            confidence=float(value.get("confidence", 0.0) or 0.0),
            mastery=float(value.get("mastery", 50.0) or 50.0),
            specialization=_float(value.get("specialization")),
            classification=str(value.get("classification", "常用英雄")),
            dimensions={str(k): _float(v) for k, v in (value.get("dimensions") or {}).items()},
            confidence_components={str(k): float(v or 0.0) for k, v in (value.get("confidence_components") or {}).items()},
            observable_coverage=float(value.get("observable_coverage", 0.0) or 0.0),
            baseline_group=value.get("baseline_group"),
        )


def _float(value: Any) -> float | None:
    return None if value is None else float(value)
