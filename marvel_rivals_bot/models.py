from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class ModeStats:
    """Statistics for one explicit match scope.

    ``quick`` and ``competitive`` are intentionally separate.  The aggregate
    values on ``CareerSummary`` and ``PlayerHeroStats`` describe total usage,
    while Meta comparisons consume the competitive scope only.
    """

    matches: int | None = None
    wins: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    final_hits: int | None = None
    max_kills: int | None = None
    max_assists: int | None = None
    max_final_hits: int | None = None
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
    rank_history: dict[str, int] = field(default_factory=dict)

    @property
    def rank_game_season_levels(self) -> dict[str, int]:
        """Compatibility alias for the CN season-code to rank-level map."""

        return self.rank_history

    @property
    def rank_levels_by_season(self) -> dict[str, int]:
        """Compatibility alias used by older history-oriented callers."""

        return self.rank_history

    @property
    def rank_game_seasons(self) -> dict[str, int]:
        """Compatibility alias for callers using the upstream field name."""

        return self.rank_history


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
    competitive: ModeStats = field(default_factory=ModeStats)

    def __post_init__(self) -> None:
        # ``ranked`` was the name used by the first split-mode release.  Keep
        # accepting it for integrations while making Competitive canonical.
        if _mode_is_empty(self.competitive) and not _mode_is_empty(self.ranked):
            self.competitive = self.ranked
        self.ranked = self.competitive
        if self.matches is None:
            self.matches = _sum_optional(self.quick.matches, self.competitive.matches)
        if self.wins is None:
            self.wins = _sum_optional(self.quick.wins, self.competitive.wins)
        if self.win_rate is None and self.matches and self.wins is not None:
            self.win_rate = self.wins * 100 / self.matches


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
    """Per-hero usage split into total, quick, and competitive scopes."""

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
    competitive: ModeStats = field(default_factory=ModeStats)

    def __post_init__(self) -> None:
        """Keep scalar total fields compatible with the explicit total scope."""

        if _mode_is_empty(self.competitive) and not _mode_is_empty(self.ranked):
            self.competitive = self.ranked
        self.ranked = self.competitive

        # When the two explicit scopes are available, total usage is derived
        # from them instead of trusting an ambiguous aggregate endpoint.
        if (
            self.quick.matches is not None
            and self.competitive.matches is not None
        ) or (self.total.matches is None and (self.quick.matches is not None or self.competitive.matches is not None)):
            self.total.matches = _sum_optional(self.quick.matches, self.competitive.matches)
        if (
            self.quick.wins is not None
            and self.competitive.wins is not None
        ) or (self.total.wins is None and (self.quick.wins is not None or self.competitive.wins is not None)):
            self.total.wins = _sum_optional(self.quick.wins, self.competitive.wins)
        if self.total.matches and self.total.wins is not None:
            self.total.win_rate = self.total.wins * 100 / self.total.matches
        if (
            self.quick.play_time_seconds is not None
            and self.competitive.play_time_seconds is not None
        ) or (
            self.total.play_time_seconds is None
            and (self.quick.play_time_seconds is not None or self.competitive.play_time_seconds is not None)
        ):
            self.total.play_time_seconds = _sum_optional(
                self.quick.play_time_seconds, self.competitive.play_time_seconds
            )

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
    # new code should use the explicit total/quick/competitive fields.
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
        return self.competitive.kills if self.competitive.kills is not None else self.quick.kills

    @property
    def play_time_seconds(self) -> float | None:
        return self.total_play_time_seconds


def _mode_is_empty(mode: ModeStats) -> bool:
    return all(value is None for value in vars(mode).values()) if hasattr(mode, "__dict__") else all(
        getattr(mode, field_name) is None
        for field_name in ModeStats.__dataclass_fields__
    )


def _sum_optional(*values: int | float | None) -> int | float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


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
    role: str | None = None
    role_label: str | None = None


@dataclass(slots=True)
class RecentMatch:
    match_uid: str
    result: str = "?"
    hero_name: str = "未知英雄"
    kills: int | str = "-"
    deaths: int | str = "-"
    assists: int | str = "-"
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class MatchSummaryPage:
    """One page returned by the CN ``loadSummary`` endpoint."""

    match_info: list[dict[str, Any]] = field(default_factory=list)
    page: int = 0
    page_size: int = 100
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class DailyModeStats:
    """Aggregated statistics for one daily game-mode bucket."""

    matches: int = 0
    wins: int = 0
    losses: int = 0
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    hero_damage: int | None = None
    healing: int | None = None
    damage_taken: int | None = None
    play_time_seconds: float = 0
    damage_samples: int = field(default=0, repr=False)
    healing_samples: int = field(default=0, repr=False)
    damage_taken_samples: int = field(default=0, repr=False)

    @property
    def win_rate(self) -> float | None:
        return self.wins * 100 / self.matches if self.matches else None

    @property
    def average_kills(self) -> float | None:
        return self.kills / self.matches if self.matches else None

    @property
    def average_deaths(self) -> float | None:
        return self.deaths / self.matches if self.matches else None

    @property
    def average_assists(self) -> float | None:
        return self.assists / self.matches if self.matches else None

    @property
    def average_hero_damage(self) -> float | None:
        return self.hero_damage / self.damage_samples if self.hero_damage is not None and self.damage_samples else None

    @property
    def average_healing(self) -> float | None:
        return self.healing / self.healing_samples if self.healing is not None and self.healing_samples else None

    @property
    def average_damage_taken(self) -> float | None:
        return self.damage_taken / self.damage_taken_samples if self.damage_taken is not None and self.damage_taken_samples else None

    @property
    def kda(self) -> str:
        return f"{self.kills} / {self.deaths} / {self.assists}"

    @property
    def incomplete_metrics(self) -> tuple[str, ...]:
        missing: list[str] = []
        if 0 < self.damage_samples < self.matches:
            missing.append("伤害")
        if 0 < self.healing_samples < self.matches:
            missing.append("治疗")
        if 0 < self.damage_taken_samples < self.matches:
            missing.append("承伤")
        return tuple(missing)


@dataclass(slots=True)
class DailyMatch:
    """Normalized target-player view of one match detail."""

    match_uid: str
    timestamp: int | None = None
    game_mode_id: int | None = None
    play_mode_id: int | None = None
    duration_seconds: float = 0
    hero_id: str | None = None
    is_win: bool | None = None
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    hero_damage: int | None = None
    healing: int | None = None
    damage_taken: int | None = None
    player_name: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class DailyHeroStats:
    hero_id: str
    hero_name: str
    matches: int = 0
    wins: int = 0
    losses: int = 0
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    play_time_seconds: float = 0
    hero_damage: int | None = None
    healing: int | None = None
    damage_taken: int | None = None
    damage_samples: int = field(default=0, repr=False)
    healing_samples: int = field(default=0, repr=False)
    damage_taken_samples: int = field(default=0, repr=False)

    @property
    def win_rate(self) -> float | None:
        return self.wins * 100 / self.matches if self.matches else None

@dataclass(slots=True)
class DailyReport:
    uid: str
    player_name: str
    date: date
    timezone: str
    season: str
    total: DailyModeStats = field(default_factory=DailyModeStats)
    quick: DailyModeStats = field(default_factory=DailyModeStats)
    competitive: DailyModeStats = field(default_factory=DailyModeStats)
    other: DailyModeStats = field(default_factory=DailyModeStats)
    heroes: list[DailyHeroStats] = field(default_factory=list)
    matches: list[DailyMatch] = field(default_factory=list)
