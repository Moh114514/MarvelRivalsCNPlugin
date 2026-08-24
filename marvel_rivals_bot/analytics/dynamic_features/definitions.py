"""Observed DynamicFields definitions.

The keys are collected and persisted now, but remain disabled for Rating V2
until their gameplay semantics are verified.
"""

from __future__ import annotations

from .models import FeatureDefinition


_UNKNOWN_1031_KEYS = (
    "Feature_103102:ally_hit",
    "Feature_103102:chaos_hit",
    "Feature_103102:summoner_hit",
    "Feature_103101:hero_hit",
    "Feature_103102:hero_hit",
    "Feature_103101:hero_crit_hit",
    "Feature_103102:real_hit_hero_cnt",
    "Feature_103102:enemy_hit",
    "Feature_103102:shield_hit",
    "Feature_103101",
    "Feature_103103",
    "Feature_103102",
    "Feature_103102:use_cnt",
)

DYNAMIC_FEATURE_DEFINITIONS: tuple[FeatureDefinition, ...] = (
    *(FeatureDefinition(1031, key, None, "unknown") for key in _UNKNOWN_1031_KEYS),
    FeatureDefinition(1058, "Feature_105801", None, "utility"),
    FeatureDefinition(1058, "Feature_105802", None, "utility"),
    FeatureDefinition(1058, "Feature_105803", None, "utility"),
)

FEATURE_DEFINITIONS: dict[tuple[int, str], FeatureDefinition] = {
    (item.hero_id, item.key): item for item in DYNAMIC_FEATURE_DEFINITIONS
}


__all__ = ["DYNAMIC_FEATURE_DEFINITIONS", "FEATURE_DEFINITIONS"]
