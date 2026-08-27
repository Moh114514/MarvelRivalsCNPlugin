"""Pure Player Rating V2 calculations.

The package deliberately has no transport, cache, AstrBot, or rendering
dependencies.  ``signature.py`` adapts its normalized ViewModels into this
engine and keeps the existing public result fields compatible.
"""

from .engine import HeroRatingEngine
from .models import HeroRatingResult, RatingContext, RatingHeroSnapshot, SeasonRatingSnapshot
from .specialization import SpecializationEvidencePolicy
from .temporal import (
    TEMPORAL_DECLINING,
    TEMPORAL_FORMER,
    TEMPORAL_RISING,
    TEMPORAL_STABLE,
    TEMPORAL_VERIFY,
    TemporalRating,
    apply_temporal_ratings,
    calculate_freshness,
    calculate_temporal_rating,
    classify_temporal_state,
)

__all__ = [
    "HeroRatingEngine",
    "HeroRatingResult",
    "RatingContext",
    "RatingHeroSnapshot",
    "SeasonRatingSnapshot",
    "SpecializationEvidencePolicy",
    "TemporalRating",
    "TEMPORAL_DECLINING",
    "TEMPORAL_FORMER",
    "TEMPORAL_RISING",
    "TEMPORAL_STABLE",
    "TEMPORAL_VERIFY",
    "apply_temporal_ratings",
    "calculate_freshness",
    "calculate_temporal_rating",
    "classify_temporal_state",
]
