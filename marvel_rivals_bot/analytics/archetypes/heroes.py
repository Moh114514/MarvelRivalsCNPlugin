"""The v1 tactical prior for every currently known hero.

The mapping deliberately contains no metric weights.  Weights live in
``profiles.py`` so one algorithmic change applies consistently to a profile.
"""

from __future__ import annotations

from .models import CombatStyle, HeroArchetype, MetricProfileId, TacticalFunction
from ...reference.heroes import HERO_ID_MAP, HERO_ROLE_MAP
from .profiles import METRIC_PROFILES


def _a(
    hero_id: int,
    primary: CombatStyle,
    function: TacticalFunction,
    profile: MetricProfileId,
    secondary: CombatStyle | None = None,
    *tags: str,
) -> HeroArchetype:
    return HeroArchetype(hero_id, primary, secondary, function, profile, tuple(tags))


HERO_ARCHETYPES: dict[int, HeroArchetype] = {
    # Vanguard
    1011: _a(1011, CombatStyle.BRAWL, TacticalFunction.BRUISER, MetricProfileId.VANGUARD_BRAWL, CombatStyle.DIVE, "disruptor"),
    1018: _a(1018, CombatStyle.POKE, TacticalFunction.ANCHOR, MetricProfileId.VANGUARD_ANCHOR, CombatStyle.BRAWL, "protection"),
    1022: _a(1022, CombatStyle.BRAWL, TacticalFunction.INITIATOR, MetricProfileId.VANGUARD_DIVE, CombatStyle.DIVE, "disruptor"),
    1027: _a(1027, CombatStyle.BRAWL, TacticalFunction.ZONE, MetricProfileId.VANGUARD_ZONE, CombatStyle.POKE, "bunker"),
    1035: _a(1035, CombatStyle.DIVE, TacticalFunction.INITIATOR, MetricProfileId.VANGUARD_DIVE, CombatStyle.BRAWL),
    1037: _a(1037, CombatStyle.POKE, TacticalFunction.ANCHOR, MetricProfileId.VANGUARD_ANCHOR, CombatStyle.BRAWL, "pressure"),
    1039: _a(1039, CombatStyle.BRAWL, TacticalFunction.BRUISER, MetricProfileId.VANGUARD_BRAWL, CombatStyle.DIVE),
    1042: _a(1042, CombatStyle.POKE, TacticalFunction.ZONE, MetricProfileId.VANGUARD_ZONE, CombatStyle.BRAWL, "anti_dive"),
    1051: _a(1051, CombatStyle.BRAWL, TacticalFunction.BRUISER, MetricProfileId.VANGUARD_BRAWL, None, "anti_dive"),
    1053: _a(1053, CombatStyle.POKE, TacticalFunction.ANCHOR, MetricProfileId.VANGUARD_ANCHOR, CombatStyle.BRAWL, "controller"),
    1056: _a(1056, CombatStyle.DIVE, TacticalFunction.INITIATOR, MetricProfileId.VANGUARD_DIVE, CombatStyle.BRAWL, "mobile"),
    10571: _a(10571, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.VANGUARD_PRESSURE, CombatStyle.BRAWL, "flex"),
    1062: _a(1062, CombatStyle.BRAWL, TacticalFunction.BRUISER, MetricProfileId.VANGUARD_BRAWL, None, "heavy"),
    1065: _a(1065, CombatStyle.BRAWL, TacticalFunction.BRUISER, MetricProfileId.VANGUARD_BRAWL, CombatStyle.DIVE, "disruptor"),
    1066: _a(1066, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.VANGUARD_PRESSURE, CombatStyle.BRAWL, "mid_range"),
    # Duelist
    1014: _a(1014, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.POKE_PRESSURE, CombatStyle.BRAWL),
    1015: _a(1015, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.POKE_PRESSURE, CombatStyle.BRAWL, "aura"),
    1017: _a(1017, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.POKE_PRESSURE, CombatStyle.BRAWL, "aoe_zone"),
    1021: _a(1021, CombatStyle.POKE, TacticalFunction.PICK, MetricProfileId.POKE_PICK),
    1024: _a(1024, CombatStyle.POKE, TacticalFunction.PICK, MetricProfileId.POKE_PICK, None, "burst_pressure"),
    1026: _a(1026, CombatStyle.DIVE, TacticalFunction.ASSASSIN, MetricProfileId.DIVE_ASSASSIN),
    1029: _a(1029, CombatStyle.BRAWL, TacticalFunction.SKIRMISHER, MetricProfileId.MOBILE_SKIRMISHER, CombatStyle.DIVE),
    1030: _a(1030, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.POKE_PRESSURE),
    1032: _a(1032, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.POKE_PRESSURE, None, "artillery"),
    1033: _a(1033, CombatStyle.POKE, TacticalFunction.PICK, MetricProfileId.POKE_PICK),
    1034: _a(1034, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.POKE_PRESSURE),
    1036: _a(1036, CombatStyle.DIVE, TacticalFunction.ASSASSIN, MetricProfileId.DIVE_ASSASSIN, None, "finisher", "backline_dive"),
    1038: _a(1038, CombatStyle.BRAWL, TacticalFunction.SKIRMISHER, MetricProfileId.MOBILE_SKIRMISHER, CombatStyle.DIVE),
    1040: _a(1040, CombatStyle.BRAWL, TacticalFunction.BRUISER, MetricProfileId.BRAWL_BRUISER),
    1041: _a(1041, CombatStyle.BRAWL, TacticalFunction.PICK, MetricProfileId.POKE_PICK, CombatStyle.POKE, "burst"),
    1043: _a(1043, CombatStyle.DIVE, TacticalFunction.SKIRMISHER, MetricProfileId.MOBILE_SKIRMISHER, CombatStyle.POKE),
    1044: _a(1044, CombatStyle.BRAWL, TacticalFunction.BRUISER, MetricProfileId.BRAWL_BRUISER, CombatStyle.POKE),
    1045: _a(1045, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.POKE_PRESSURE),
    1048: _a(1048, CombatStyle.DIVE, TacticalFunction.ASSASSIN, MetricProfileId.DIVE_ASSASSIN, CombatStyle.POKE),
    1049: _a(1049, CombatStyle.BRAWL, TacticalFunction.TANK_BUSTER, MetricProfileId.TANK_BUSTER),
    1052: _a(1052, CombatStyle.BRAWL, TacticalFunction.BRUISER, MetricProfileId.BRAWL_BRUISER, CombatStyle.DIVE),
    1054: _a(1054, CombatStyle.POKE, TacticalFunction.PICK, MetricProfileId.POKE_PICK),
    1055: _a(1055, CombatStyle.DIVE, TacticalFunction.SKIRMISHER, MetricProfileId.MOBILE_SKIRMISHER, CombatStyle.BRAWL),
    10572: _a(10572, CombatStyle.BRAWL, TacticalFunction.SKIRMISHER, MetricProfileId.MOBILE_SKIRMISHER, CombatStyle.POKE, "flex"),
    1059: _a(1059, CombatStyle.POKE, TacticalFunction.PICK, MetricProfileId.POKE_PICK, CombatStyle.BRAWL),
    1061: _a(1061, CombatStyle.DIVE, TacticalFunction.ASSASSIN, MetricProfileId.DIVE_ASSASSIN),
    1063: _a(1063, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.POKE_PRESSURE),
    # Strategist
    1016: _a(1016, CombatStyle.POKE, TacticalFunction.UTILITY, MetricProfileId.UTILITY_SUPPORT, None, "bunker"),
    1020: _a(1020, CombatStyle.POKE, TacticalFunction.UTILITY, MetricProfileId.UTILITY_SUPPORT, CombatStyle.BRAWL, "tempo", "control"),
    1023: _a(1023, CombatStyle.DIVE, TacticalFunction.SUPPORT, MetricProfileId.MOBILE_SUPPORT, CombatStyle.BRAWL),
    1025: _a(1025, CombatStyle.BRAWL, TacticalFunction.UTILITY, MetricProfileId.UTILITY_SUPPORT, CombatStyle.POKE),
    1028: _a(1028, CombatStyle.POKE, TacticalFunction.PRESSURE, MetricProfileId.AGGRESSIVE_SUPPORT, CombatStyle.DIVE),
    1031: _a(1031, CombatStyle.POKE, TacticalFunction.SUPPORT, MetricProfileId.BACKLINE_SUPPORT),
    1046: _a(1046, CombatStyle.POKE, TacticalFunction.SUPPORT, MetricProfileId.BACKLINE_SUPPORT),
    1047: _a(1047, CombatStyle.POKE, TacticalFunction.SUPPORT, MetricProfileId.MOBILE_SUPPORT, CombatStyle.DIVE, "disruptor"),
    1050: _a(1050, CombatStyle.POKE, TacticalFunction.UTILITY, MetricProfileId.UTILITY_SUPPORT, CombatStyle.BRAWL, "protection"),
    10573: _a(10573, CombatStyle.POKE, TacticalFunction.UTILITY, MetricProfileId.AGGRESSIVE_SUPPORT, CombatStyle.BRAWL, "aggressive"),
    1058: _a(1058, CombatStyle.BRAWL, TacticalFunction.UTILITY, MetricProfileId.AGGRESSIVE_SUPPORT, CombatStyle.DIVE, "tempo"),
    1060: _a(1060, CombatStyle.BRAWL, TacticalFunction.SUPPORT, MetricProfileId.AGGRESSIVE_SUPPORT, CombatStyle.DIVE),
    1064: _a(1064, CombatStyle.BRAWL, TacticalFunction.UTILITY, MetricProfileId.AGGRESSIVE_SUPPORT, CombatStyle.POKE, "zone"),
}


_PROFILE_ROLES = {
    MetricProfileId.DIVE_ASSASSIN: "duelist",
    MetricProfileId.MOBILE_SKIRMISHER: "duelist",
    MetricProfileId.POKE_PICK: "duelist",
    MetricProfileId.POKE_PRESSURE: "duelist",
    MetricProfileId.BRAWL_BRUISER: "duelist",
    MetricProfileId.TANK_BUSTER: "duelist",
    MetricProfileId.VANGUARD_ANCHOR: "vanguard",
    MetricProfileId.VANGUARD_ZONE: "vanguard",
    MetricProfileId.VANGUARD_BRAWL: "vanguard",
    MetricProfileId.VANGUARD_DIVE: "vanguard",
    MetricProfileId.VANGUARD_PRESSURE: "vanguard",
    MetricProfileId.BACKLINE_SUPPORT: "strategist",
    MetricProfileId.AGGRESSIVE_SUPPORT: "strategist",
    MetricProfileId.MOBILE_SUPPORT: "strategist",
    MetricProfileId.UTILITY_SUPPORT: "strategist",
}


def validate_archetypes() -> None:
    if set(HERO_ARCHETYPES) != set(HERO_ROLE_MAP) or set(HERO_ARCHETYPES) != set(HERO_ID_MAP):
        raise ValueError("HERO_ARCHETYPES 必须覆盖全部官方英雄且不能新增未知 ID")
    for hero_id, archetype in HERO_ARCHETYPES.items():
        if archetype.hero_id != hero_id:
            raise ValueError(f"英雄 {hero_id} 的 Archetype ID 不一致")
        profile = METRIC_PROFILES.get(archetype.metric_profile)
        if profile is None:
            raise ValueError(f"英雄 {hero_id} 使用了不存在的 Metric Profile")
        if _PROFILE_ROLES[archetype.metric_profile] != HERO_ROLE_MAP[hero_id]:
            raise ValueError(f"英雄 {hero_id} 的官方职责与 Metric Profile 冲突")
        if archetype.secondary_style == archetype.primary_style:
            raise ValueError(f"英雄 {hero_id} 的主次 Combat Style 不能相同")
        if not isinstance(archetype.tags, tuple):
            raise ValueError(f"英雄 {hero_id} 的 tags 必须是 tuple")


validate_archetypes()


def get_archetype(hero_id: int | str) -> HeroArchetype | None:
    try:
        return HERO_ARCHETYPES.get(int(hero_id))
    except (TypeError, ValueError):
        return None


__all__ = ["HERO_ARCHETYPES", "get_archetype", "validate_archetypes"]
