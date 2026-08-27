"""Frozen Rating V2 calibration parameters.

These constants mirror the currently shipped algorithm.  Changing one is a
calibration change and must be accompanied by an explicit schema-version
decision; product labels and rendering must not change them implicitly.
"""

RATING_V2_OUTCOME_WEIGHT = 0.50
RATING_V2_COMBAT_WEIGHT = 0.35
RATING_V2_CONSISTENCY_WEIGHT = 0.15
RATING_V2_MASTERY_PERFORMANCE_WEIGHT = 0.75
RATING_V2_MASTERY_EXPERIENCE_WEIGHT = 0.25

__all__ = [
    "RATING_V2_OUTCOME_WEIGHT",
    "RATING_V2_COMBAT_WEIGHT",
    "RATING_V2_CONSISTENCY_WEIGHT",
    "RATING_V2_MASTERY_PERFORMANCE_WEIGHT",
    "RATING_V2_MASTERY_EXPERIENCE_WEIGHT",
]
