"""Hero tactical archetype public API."""

from .heroes import HERO_ARCHETYPES, get_archetype, validate_archetypes
from .models import (
    CombatStyle,
    HeroArchetype,
    MetricDimension,
    MetricProfile,
    MetricProfileId,
    TacticalFunction,
)
from .profiles import METRIC_PROFILES, validate_metric_profiles
from .presentation import (
    FUNCTION_LABELS,
    ROLE_LABELS,
    STYLE_LABELS,
    archetype_labels,
    archetype_summary,
    product_status,
)

__all__ = [
    "CombatStyle",
    "HeroArchetype",
    "MetricDimension",
    "MetricProfile",
    "MetricProfileId",
    "TacticalFunction",
    "HERO_ARCHETYPES",
    "METRIC_PROFILES",
    "get_archetype",
    "validate_archetypes",
    "validate_metric_profiles",
    "archetype_labels",
    "archetype_summary",
    "product_status",
    "FUNCTION_LABELS",
    "ROLE_LABELS",
    "STYLE_LABELS",
]
