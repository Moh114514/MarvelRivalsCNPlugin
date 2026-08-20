"""Public career-analysis boundary.

The implementation remains in ``signature.py`` during the compatibility
migration so older integrations keep importing ``PlayerSignatureService``.
New code should import the explicit names from this module.
"""

from .models import AnalysisScope, HeroPerformanceAnalysis, NormalizedModeStats, PlayerCareerAnalysis
from .signature import CareerAnalysisCache, PlayerCareerAnalysisService, SeasonAggregationPolicy

__all__ = [
    "AnalysisScope",
    "CareerAnalysisCache",
    "HeroPerformanceAnalysis",
    "NormalizedModeStats",
    "PlayerCareerAnalysis",
    "PlayerCareerAnalysisService",
    "SeasonAggregationPolicy",
]
