from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ModeStats:
    """Statistics for one explicit match scope.

    ``quick`` and ``ranked`` are intentionally separate.  The aggregate
    values on ``CareerSummary`` and ``PlayerHeroStats`` describe total usage,
    while Meta comparisons consume the ranked scope only.
    """

    matches: int | None = None
    wins: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    win_rate: float | None = None
    damage: int | None = None
    hero_damage: int | None = None
    heal: int | None = None
    damage_taken: int | None = None
    hit_rate: float | None = None
    play_time_seconds: float | None = None
    mvp: int | None = None
    svp: int | None = None


@dataclass(slots=True)
class PlayerProfile:
    uid: str
    name: str = "未知"
    aid: str = ""
    level: int | None = None
    club_team_name: str = ""
    rank_game_season: str = ""
    rank_level: int | None = None


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
    quick: ModeStats = field(default_factory=ModeStats)
    ranked: ModeStats = field(default_factory=ModeStats)


@dataclass(slots=True)
class HeroStat:
    hero_id: str
    hero_name: str = "未知英雄"
    matches: int | None = None
    wins: int | None = None
    kills: int | None = None
    win_rate: float | None = None
    play_time_seconds: float | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class PlayerHeroStats:
    """Per-hero usage split into total, quick, and ranked scopes."""

    hero_id: str
    hero_name: str = "未知英雄"
    total_matches: int | None = None
    total_wins: int | None = None
    total_win_rate: float | None = None
    total_play_time_seconds: float | None = None
    quick: ModeStats = field(default_factory=ModeStats)
    ranked: ModeStats = field(default_factory=ModeStats)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    total: ModeStats = field(default_factory=ModeStats)

    def __post_init__(self) -> None:
        """Keep scalar total fields compatible with the explicit total scope."""

        pairs = (
            ("matches", "total_matches"),
            ("wins", "total_wins"),
            ("win_rate", "total_win_rate"),
            ("play_time_seconds", "total_play_time_seconds"),
        )
        for scope_name, scalar_name in pairs:
            scope_value = getattr(self.total, scope_name)
            scalar_value = getattr(self, scalar_name)
            if scope_value is None and scalar_value is not None:
                setattr(self.total, scope_name, scalar_value)
            elif scalar_value is None and scope_value is not None:
                setattr(self, scalar_name, scope_value)

    # Compatibility accessors keep older presenters and integrations usable;
    # new code should use the explicit total/quick/ranked fields.
    @property
    def matches(self) -> int | None:
        return self.total_matches

    @property
    def wins(self) -> int | None:
        return self.total_wins

    @property
    def win_rate(self) -> float | None:
        return self.total_win_rate

    @property
    def kills(self) -> int | None:
        return self.ranked.kills if self.ranked.kills is not None else self.quick.kills

    @property
    def play_time_seconds(self) -> float | None:
        return self.total_play_time_seconds


@dataclass(slots=True)
class PlayerStats:
    profile: PlayerProfile
    summary: CareerSummary = field(default_factory=CareerSummary)
    heroes: list[PlayerHeroStats | HeroStat] = field(default_factory=list)
    season: str = "19"
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class HeroQueryResult:
    uid: str
    hero_id: str
    hero_name: str
    season: str
    payload: dict[str, Any] = field(default_factory=dict, repr=False)
    stats: PlayerHeroStats | HeroStat | None = None


@dataclass(slots=True)
class RecentMatch:
    match_uid: str
    result: str = "?"
    hero_name: str = "未知英雄"
    kills: int | str = "-"
    deaths: int | str = "-"
    assists: int | str = "-"
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
