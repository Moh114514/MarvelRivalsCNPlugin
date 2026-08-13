from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PlayerProfile:
    uid: str
    name: str = "未知"
    aid: str = ""
    level: int | None = None
    club_team_name: str = ""
    rank_game_season: str = ""


@dataclass(slots=True)
class CareerSummary:
    matches: int | None = None
    wins: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    win_rate: float | None = None
    damage: int | None = None
    hero_damage: int | None = None


@dataclass(slots=True)
class HeroStat:
    hero_id: str
    hero_name: str = "未知英雄"
    matches: int | None = None
    win_rate: float | None = None
    play_time_seconds: float | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class PlayerStats:
    profile: PlayerProfile
    summary: CareerSummary = field(default_factory=CareerSummary)
    heroes: list[HeroStat] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class RecentMatch:
    match_uid: str
    result: str = "?"
    hero_name: str = "未知英雄"
    kills: int | str = "-"
    deaths: int | str = "-"
    assists: int | str = "-"
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
