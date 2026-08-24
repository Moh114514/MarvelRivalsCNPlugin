from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class ModeStats:
    """Statistics for one explicit match scope.

    ``quick`` and ``competitive`` are intentionally separate.  The aggregate
    values on ``CareerSummary`` and ``PlayerHeroStats`` describe total usage,
    while Meta comparisons consume the competitive scope only.
    """

    matches: int | None = None
    # CN may return an effective (non-integral) match count.  Keep the
    # rounded ``matches`` field for existing presenters and preserve the
    # source value separately for the V2 analytics layer.
    effective_matches: float | None = None
    wins: int | None = None
    effective_wins: float | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    final_hits: int | None = None
    solo_eliminations: int | None = None
    critical_eliminations: int | None = None
    main_attack_count: int | None = None
    main_attack_hits: int | None = None
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
    dynamic_sum: dict[str, float] = field(default_factory=dict)
    dynamic_max: dict[str, float] = field(default_factory=dict)

    @property
    def _per10_factor(self) -> float | None:
        return 600 / self.play_time_seconds if self.play_time_seconds and self.play_time_seconds > 0 else None

    def _per10(self, value: int | float | None) -> float | None:
        factor = self._per10_factor
        return value * factor if value is not None and factor is not None else None

    @property
    def per10_kills(self) -> float | None:
        return self._per10(self.kills)

    @property
    def per10_deaths(self) -> float | None:
        return self._per10(self.deaths)

    @property
    def per10_assists(self) -> float | None:
        return self._per10(self.assists)

    @property
    def per10_final_hits(self) -> float | None:
        return self._per10(self.final_hits)

    @property
    def per10_solo_eliminations(self) -> float | None:
        return self._per10(self.solo_eliminations)

    @property
    def per10_critical_eliminations(self) -> float | None:
        return self._per10(self.critical_eliminations)

    @property
    def main_attack_accuracy(self) -> float | None:
        if self.main_attack_count and self.main_attack_count > 0 and self.main_attack_hits is not None:
            return self.main_attack_hits * 100 / self.main_attack_count
        return None

    @property
    def effective_win_rate(self) -> float | None:
        if self.effective_matches and self.effective_wins is not None:
            return self.effective_wins * 100 / self.effective_matches
        return None

    @property
    def max_hit_rate(self) -> float | None:
        """Explicit name for the session maximum retained by ``hit_rate``."""
        return self.hit_rate

    @property
    def per10_hero_damage(self) -> float | None:
        return self._per10(self.hero_damage if self.hero_damage is not None else self.damage)

    @property
    def per10_heal(self) -> float | None:
        return self._per10(self.heal)

    @property
    def per10_damage_taken(self) -> float | None:
        return self._per10(self.damage_taken)


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
    rank_score: int | None = None
    rank_score_history: dict[str, int] = field(default_factory=dict)

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
        if self.win_rate is None:
            effective_matches = _sum_optional(
                self.quick.effective_matches,
                self.competitive.effective_matches,
            )
            effective_wins = _sum_optional(
                self.quick.effective_wins,
                self.competitive.effective_wins,
            )
            if effective_matches and effective_wins is not None:
                self.win_rate = effective_wins * 100 / effective_matches
            elif self.matches and self.wins is not None:
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
        if self.total.effective_matches and self.total.effective_wins is not None:
            self.total.win_rate = self.total.effective_wins * 100 / self.total.effective_matches
        elif self.total.matches and self.total.wins is not None:
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
        for field_name in (
            "effective_matches",
            "effective_wins",
            "kills", "deaths", "assists", "final_hits",
            "solo_eliminations", "critical_eliminations",
            "main_attack_count", "main_attack_hits",
            "damage", "hero_damage", "heal", "damage_taken", "mvp", "svp",
        ):
            if getattr(self.total, field_name) is None:
                setattr(
                    self.total,
                    field_name,
                    _sum_optional(
                        getattr(self.quick, field_name),
                        getattr(self.competitive, field_name),
                    ),
                )
        if self.total.effective_matches and self.total.effective_wins is not None:
            self.total.win_rate = self.total.effective_wins * 100 / self.total.effective_matches
        for field_name in ("max_kills", "max_assists", "max_final_hits"):
            if getattr(self.total, field_name) is None:
                values = [
                    getattr(self.quick, field_name),
                    getattr(self.competitive, field_name),
                ]
                values = [value for value in values if value is not None]
                setattr(self.total, field_name, max(values) if values else None)
        if not self.total.dynamic_sum:
            self.total.dynamic_sum = _merge_dynamic_sum(self.quick.dynamic_sum, self.competitive.dynamic_sum)
        if not self.total.dynamic_max:
            self.total.dynamic_max = _merge_dynamic_max(self.quick.dynamic_max, self.competitive.dynamic_max)

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
    return all(value is None or value == {} for value in vars(mode).values()) if hasattr(mode, "__dict__") else all(
        getattr(mode, field_name) is None or getattr(mode, field_name) == {}
        for field_name in ModeStats.__dataclass_fields__
    )


def _sum_optional(*values: int | float | None) -> int | float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _merge_dynamic_sum(*values: dict[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for mapping in values:
        for key, value in mapping.items():
            result[key] = result.get(key, 0.0) + value
    return result


def _merge_dynamic_max(*values: dict[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for mapping in values:
        for key, value in mapping.items():
            result[key] = max(result.get(key, value), value)
    return result


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
class MatchTimeWindow:
    """A server-queryable half-open window in the game timezone."""

    start_timestamp: int
    end_timestamp: int
    start_at: datetime
    end_at: datetime
    timezone: str = "Asia/Shanghai"
    label: str = ""


@dataclass(slots=True)
class WindowStats:
    """Aggregated statistics for one game-mode bucket in a time window."""

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
    final_hits: int = 0
    play_time_authoritative: bool = field(default=True, repr=False)

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
    def per10_available(self) -> bool:
        return self.play_time_authoritative and self.play_time_seconds > 0

    def _per10(self, value: int | float | None) -> float | None:
        if value is None or not self.play_time_authoritative or self.play_time_seconds <= 0:
            return None
        return value * 600 / self.play_time_seconds

    @property
    def per10_kills(self) -> float | None:
        return self._per10(self.kills)

    @property
    def per10_deaths(self) -> float | None:
        return self._per10(self.deaths)

    @property
    def per10_assists(self) -> float | None:
        return self._per10(self.assists)

    @property
    def per10_final_hits(self) -> float | None:
        return self._per10(self.final_hits)

    @property
    def per10_hero_damage(self) -> float | None:
        return self._per10(self.hero_damage)

    @property
    def per10_healing(self) -> float | None:
        return self._per10(self.healing)

    @property
    def per10_damage_taken(self) -> float | None:
        return self._per10(self.damage_taken)

    @property
    def incomplete_metrics(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.damage_samples < self.matches:
            missing.append("伤害")
        if self.healing_samples < self.matches:
            missing.append("治疗")
        if self.damage_taken_samples < self.matches:
            missing.append("承伤")
        return tuple(missing)


ROLE_ORDER = ("vanguard", "duelist", "strategist")


@dataclass(slots=True)
class RoleWindowStats(WindowStats):
    """Window statistics for one canonical hero role.

    The metric totals and sample counters are deliberately kept together so
    every role calculates its own averages instead of borrowing the overall
    match count as a denominator.
    """

    role: str = ""


@dataclass(slots=True)
class HeroMatchSlice:
    """One hero's contribution to a match, normalized from ``playerHeroes``."""

    hero_id: str
    role: str | None = None
    play_time_seconds: float = 0
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    final_hits: int | None = None
    hero_damage: int | None = None
    healing: int | None = None
    damage_taken: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class MatchPlayer:
    """The selected player's normalized fields from one match detail."""

    player_uid: str
    hero_id: str | None = None
    is_win: bool | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    hero_damage: int | None = None
    healing: int | None = None
    damage_taken: int | None = None
    player_name: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    play_time_seconds: float | None = None
    final_hits: int | None = None
    heroes: list[HeroMatchSlice] = field(default_factory=list)
    role_breakdown_valid: bool = False

    @property
    def main_hero(self) -> HeroMatchSlice | None:
        if not self.heroes:
            return None
        return max(self.heroes, key=lambda item: (item.play_time_seconds, item.hero_id))

    @property
    def hero_switch_count(self) -> int:
        return max(0, len({item.hero_id for item in self.heroes}) - 1)

    def _per10(self, value: int | float | None) -> float | None:
        if value is None or self.play_time_seconds is None or self.play_time_seconds <= 0:
            return None
        return value * 600 / self.play_time_seconds

    @property
    def per10_kills(self) -> float | None:
        return self._per10(self.kills)

    @property
    def per10_deaths(self) -> float | None:
        return self._per10(self.deaths)

    @property
    def per10_assists(self) -> float | None:
        return self._per10(self.assists)

    @property
    def per10_final_hits(self) -> float | None:
        return self._per10(self.final_hits)

    @property
    def per10_hero_damage(self) -> float | None:
        return self._per10(self.hero_damage)

    @property
    def per10_healing(self) -> float | None:
        return self._per10(self.healing)

    @property
    def per10_damage_taken(self) -> float | None:
        return self._per10(self.damage_taken)


@dataclass(slots=True)
class MatchRecord:
    """Normalized match summary + target-player detail used by presenters."""

    match_uid: str
    timestamp: int | None = None
    game_mode_id: int | None = None
    play_mode_id: int | None = None
    map_id: int | None = None
    duration_seconds: float | None = None
    player: MatchPlayer = field(default_factory=lambda: MatchPlayer(player_uid=""))
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    # These mapping-style helpers keep legacy text/card presenters working
    # while new pages consume the typed fields above.
    def get(self, key: str, default: Any = None) -> Any:
        values = self.as_mapping()
        return values.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.as_mapping()[key]

    def as_mapping(self) -> dict[str, Any]:
        value = dict(self.raw)
        scalar_values = {
            "matchUid": self.match_uid,
            "matchTimeStamp": self.timestamp,
            "gameModeId": self.game_mode_id,
            "playModeId": self.play_mode_id,
            "matchMapId": self.map_id,
            "matchPlayDuration": self.duration_seconds,
        }
        for key, item in scalar_values.items():
            if item is not None:
                value[key] = item
        player_value = value.get("matchPlayer")
        player_mapping = dict(player_value) if isinstance(player_value, dict) else {}
        player_mapping.update({
            "playerUid": self.player.player_uid or player_mapping.get("playerUid"),
            "curHeroId": self.player.hero_id if self.player.hero_id is not None else player_mapping.get("curHeroId"),
            "isWin": 1 if self.player.is_win is True else 0 if self.player.is_win is False else player_mapping.get("isWin"),
            "k": self.player.kills if self.player.kills is not None else player_mapping.get("k"),
            "d": self.player.deaths if self.player.deaths is not None else player_mapping.get("d"),
            "a": self.player.assists if self.player.assists is not None else player_mapping.get("a"),
            "lastKill": self.player.final_hits if self.player.final_hits is not None else player_mapping.get("lastKill"),
            "finalHits": self.player.final_hits if self.player.final_hits is not None else player_mapping.get("finalHits"),
            "playTime": self.player.play_time_seconds if self.player.play_time_seconds is not None else player_mapping.get("playTime"),
            "totalHeroDamage": self.player.hero_damage if self.player.hero_damage is not None else player_mapping.get("totalHeroDamage"),
            "totalHeroHeal": self.player.healing if self.player.healing is not None else player_mapping.get("totalHeroHeal"),
            "totalDamageTaken": self.player.damage_taken if self.player.damage_taken is not None else player_mapping.get("totalDamageTaken"),
            "nickName": self.player.player_name or player_mapping.get("nickName"),
        })
        if self.player.heroes and not player_mapping.get("playerHeroes"):
            player_mapping["playerHeroes"] = [
                {
                    "heroId": item.hero_id,
                    "role": item.role,
                    "playTime": item.play_time_seconds,
                    "k": item.kills,
                    "d": item.deaths,
                    "a": item.assists,
                    "lastKill": item.final_hits,
                    "totalHeroDamage": item.hero_damage,
                    "totalHeroHeal": item.healing,
                    "totalDamageTaken": item.damage_taken,
                }
                for item in self.player.heroes
            ]
        value["matchPlayer"] = player_mapping
        return value


@dataclass(slots=True)
class WindowHeroStats:
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
    usage_rate: float | None = None
    role_usage_rate: float | None = None
    damage_samples: int = field(default=0, repr=False)
    healing_samples: int = field(default=0, repr=False)
    damage_taken_samples: int = field(default=0, repr=False)
    role: str | None = None
    final_hits: int = 0
    play_time_authoritative: bool = field(default=True, repr=False)

    @property
    def win_rate(self) -> float | None:
        return self.wins * 100 / self.matches if self.matches else None

    @property
    def kda(self) -> str:
        return f"{self.kills} / {self.deaths} / {self.assists}"

    @property
    def per10_available(self) -> bool:
        return self.play_time_authoritative and self.play_time_seconds > 0

    def _per10(self, value: int | float | None) -> float | None:
        if value is None or not self.play_time_authoritative or self.play_time_seconds <= 0:
            return None
        return value * 600 / self.play_time_seconds

    @property
    def per10_kills(self) -> float | None:
        return self._per10(self.kills)

    @property
    def per10_deaths(self) -> float | None:
        return self._per10(self.deaths)

    @property
    def per10_assists(self) -> float | None:
        return self._per10(self.assists)

    @property
    def per10_final_hits(self) -> float | None:
        return self._per10(self.final_hits)

    @property
    def per10_hero_damage(self) -> float | None:
        return self._per10(self.hero_damage)

    @property
    def per10_healing(self) -> float | None:
        return self._per10(self.healing)

    @property
    def per10_damage_taken(self) -> float | None:
        return self._per10(self.damage_taken)

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
    def incomplete_metrics(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.damage_samples < self.matches:
            missing.append("伤害")
        if self.healing_samples < self.matches:
            missing.append("治疗")
        if self.damage_taken_samples < self.matches:
            missing.append("承伤")
        return tuple(missing)


@dataclass(slots=True)
class MatchWindowReport:
    """Stable view model shared by daily and arbitrary time-window queries."""

    uid: str
    player_name: str
    window: MatchTimeWindow
    total: WindowStats = field(default_factory=WindowStats)
    quick: WindowStats = field(default_factory=WindowStats)
    competitive: WindowStats = field(default_factory=WindowStats)
    other: WindowStats = field(default_factory=WindowStats)
    heroes: list[WindowHeroStats] = field(default_factory=list)
    matches: list[MatchRecord] = field(default_factory=list)
    season: str = ""
    roles: dict[str, RoleWindowStats] = field(
        default_factory=lambda: {role: RoleWindowStats(role=role) for role in ROLE_ORDER}
    )

    @property
    def heroes_by_role(self) -> dict[str, list[WindowHeroStats]]:
        grouped: dict[str, list[WindowHeroStats]] = {role: [] for role in ROLE_ORDER}
        unknown: list[WindowHeroStats] = []
        for hero in self.heroes:
            if hero.role in grouped:
                grouped[hero.role].append(hero)
            else:
                unknown.append(hero)
        if unknown:
            grouped["unknown"] = unknown
        return grouped

    @property
    def date(self) -> date:
        """Compatibility view for the previous DailyReport API."""

        return self.window.start_at.date()

    @property
    def timezone(self) -> str:
        return self.window.timezone


# Compatibility aliases for integrations shipped before the generic window
# model.  New code should use MatchWindowReport/WindowStats/WindowHeroStats/
# MatchRecord directly.
DailyModeStats = WindowStats
DailyMatch = MatchRecord
DailyHeroStats = WindowHeroStats
DailyReport = MatchWindowReport
