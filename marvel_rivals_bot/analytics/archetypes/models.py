"""Typed models for the hero tactical archetype layer.

Official roles remain owned by ``reference.heroes``.  These values only
describe how an already-known hero is expected to create value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CombatStyle(str, Enum):
    DIVE = "dive"
    BRAWL = "brawl"
    POKE = "poke"


class TacticalFunction(str, Enum):
    ASSASSIN = "assassin"
    SKIRMISHER = "skirmisher"
    PICK = "pick"
    PRESSURE = "pressure"
    BRUISER = "bruiser"
    TANK_BUSTER = "tank_buster"
    ANCHOR = "anchor"
    ZONE = "zone"
    INITIATOR = "initiator"
    UTILITY = "utility"
    SUPPORT = "support"


class MetricDimension(str, Enum):
    FIN = "fin"
    PRS = "prs"
    SUR = "sur"
    TEAM = "team"
    HEAL = "heal"
    FRONT = "front"
    UTIL = "util"
    MECH = "mech"


class MetricProfileId(str, Enum):
    DIVE_ASSASSIN = "DIVE_ASSASSIN"
    MOBILE_SKIRMISHER = "MOBILE_SKIRMISHER"
    POKE_PICK = "POKE_PICK"
    POKE_PRESSURE = "POKE_PRESSURE"
    BRAWL_BRUISER = "BRAWL_BRUISER"
    TANK_BUSTER = "TANK_BUSTER"
    VANGUARD_ANCHOR = "VANGUARD_ANCHOR"
    VANGUARD_ZONE = "VANGUARD_ZONE"
    VANGUARD_BRAWL = "VANGUARD_BRAWL"
    VANGUARD_DIVE = "VANGUARD_DIVE"
    VANGUARD_PRESSURE = "VANGUARD_PRESSURE"
    BACKLINE_SUPPORT = "BACKLINE_SUPPORT"
    AGGRESSIVE_SUPPORT = "AGGRESSIVE_SUPPORT"
    MOBILE_SUPPORT = "MOBILE_SUPPORT"
    UTILITY_SUPPORT = "UTILITY_SUPPORT"


@dataclass(frozen=True, slots=True)
class MetricProfile:
    profile_id: MetricProfileId
    weights: tuple[tuple[MetricDimension, float], ...]

    @property
    def weight_map(self) -> dict[MetricDimension, float]:
        return dict(self.weights)

    @property
    def total_weight(self) -> float:
        return sum(weight for _dimension, weight in self.weights)

    def weight(self, dimension: MetricDimension) -> float:
        return self.weight_map.get(dimension, 0.0)


@dataclass(frozen=True, slots=True)
class HeroArchetype:
    hero_id: int
    primary_style: CombatStyle
    secondary_style: CombatStyle | None
    function: TacticalFunction
    metric_profile: MetricProfileId
    tags: tuple[str, ...] = ()

