"""Observed DynamicFields definitions.

The keys are collected and persisted now, but remain disabled for Rating V2
until their gameplay semantics are verified.
"""

from __future__ import annotations

from .models import FeatureDefinition


DYNAMIC_FEATURE_DEFINITIONS: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(1031, "Feature_103102:hero_hit", None, "utility"),
    FeatureDefinition(1031, "Feature_103101:hero_crit_hit", None, "utility"),
    FeatureDefinition(1031, "Feature_103102:real_hit_hero_cnt", None, "utility"),
    FeatureDefinition(1031, "Feature_103102:enemy_hit", None, "utility"),
    FeatureDefinition(1031, "Feature_103102:shield_hit", None, "utility"),
    FeatureDefinition(1031, "Feature_103101", None, "utility"),
    FeatureDefinition(1031, "Feature_103103", None, "utility"),
    FeatureDefinition(1031, "Feature_103102", None, "utility"),
    FeatureDefinition(1031, "Feature_103102:use_cnt", None, "utility"),
    FeatureDefinition(1058, "Feature_105801", None, "utility"),
    FeatureDefinition(1058, "Feature_105802", None, "utility"),
    FeatureDefinition(1058, "Feature_105803", None, "utility"),
)

FEATURE_DEFINITIONS: dict[tuple[int, str], FeatureDefinition] = {
    (item.hero_id, item.key): item for item in DYNAMIC_FEATURE_DEFINITIONS
}


__all__ = ["DYNAMIC_FEATURE_DEFINITIONS", "FEATURE_DEFINITIONS"]
