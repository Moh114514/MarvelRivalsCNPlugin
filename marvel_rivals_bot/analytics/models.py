"""Stable ViewModels for player and global Meta comparisons."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING

from ..meta.models import HeroMetaOverview
from ..reference.seasons import season_identity_from_cn_code

if TYPE_CHECKING:
    from .rating.models import HeroRatingResult


@dataclass(slots=True)
class PlayerHeroMetaComparison:
    """One player's explicit-mode result next to the same-rank Meta result.

    The ``personal_*`` and ``ranked_*`` fields remain constructor-compatible
    aliases for clients of the first release.  New code should use the
    ``total_*`` / ``competitive_*`` names, which make the comparison scope
    unambiguous.
    """

    hero_id: str
    hero_name: str
    personal_matches: int | None = None
    personal_wins: int | None = None
    personal_win_rate: float | None = None
    meta_matches: int | None = None
    meta_win_rate: float | None = None
    meta_pick_rate: float | None = None
    meta_ban_rate: float | None = None
    win_rate_delta: float | None = None
    total_matches: int | None = 0
    quick_matches: int | None = 0
    ranked_matches: int | None = 0
    ranked_wins: int | None = None
    ranked_win_rate: float | None = None
    ranked_share: float | None = None
    competitive_matches: int | None = None
    competitive_wins: int | None = None
    competitive_win_rate: float | None = None
    competitive_share: float | None = None
    competitive_win_rate_delta: float | None = None

    def __post_init__(self) -> None:
        if not self.total_matches and self.personal_matches is not None:
            self.total_matches = self.personal_matches
        if self.competitive_matches is None and self.ranked_matches is not None:
            self.competitive_matches = self.ranked_matches
        if self.competitive_wins is None:
            self.competitive_wins = self.ranked_wins if self.ranked_wins is not None else self.personal_wins
        if self.competitive_win_rate is None:
            self.competitive_win_rate = (
                self.ranked_win_rate if self.ranked_win_rate is not None else self.personal_win_rate
            )
        if self.competitive_share is None:
            self.competitive_share = self.ranked_share
        if self.competitive_win_rate_delta is None:
            self.competitive_win_rate_delta = self.win_rate_delta

        # Populate old aliases from canonical values for old formatters and
        # integrations that still read them.
        self.personal_matches = self.total_matches
        self.personal_wins = self.competitive_wins
        self.personal_win_rate = self.competitive_win_rate
        self.ranked_matches = self.competitive_matches
        self.ranked_wins = self.competitive_wins
        self.ranked_win_rate = self.competitive_win_rate
        self.ranked_share = self.competitive_share
        self.win_rate_delta = self.competitive_win_rate_delta


@dataclass(slots=True)
class PlayerMetaProfile:
    """Player context plus the already-calculated Meta ViewModels."""

    uid: str
    player_name: str
    cn_rank_label: str
    cn_rank_level: int
    meta_rank_code: str
    meta_rank_label: str
    season_code: str
    season_label: str
    source: str
    source_timestamp: datetime | None
    fetched_at: datetime | None
    stale: bool
    environment: HeroMetaOverview | None = None
    hero_pool: tuple[PlayerHeroMetaComparison, ...] = field(default_factory=tuple)
    signature_heroes: tuple[PlayerHeroMetaComparison, ...] = field(default_factory=tuple)
    minimum_matches: int = 20
    minimum_ranked_matches: int = 5

    @property
    def minimum_competitive_matches(self) -> int:
        return self.minimum_ranked_matches


@dataclass(slots=True)
class NormalizedModeStats:
    """Additive per-mode HeroCareer statistics used by career analysis."""

    matches: int | None = None
    effective_matches: float | None = None
    wins: int | None = None
    kills: int | None = None
    final_hits: int | None = None
    solo_eliminations: int | None = None
    critical_eliminations: int | None = None
    main_attack_count: int | None = None
    main_attack_hits: int | None = None
    deaths: int | None = None
    assists: int | None = None
    hero_damage: int | None = None
    heal: int | None = None
    damage_taken: int | None = None
    play_time: float | None = None
    mvp: int | None = None
    svp: int | None = None
    dynamic_sum: dict[str, float] = field(default_factory=dict)
    dynamic_max: dict[str, float] = field(default_factory=dict)

    def _per10(self, value: int | float | None) -> float | None:
        if value is None or self.play_time is None or self.play_time <= 0:
            return None
        return value * 600 / self.play_time

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
    def per10_hero_damage(self) -> float | None:
        return self._per10(self.hero_damage)

    @property
    def per10_heal(self) -> float | None:
        return self._per10(self.heal)

    @property
    def per10_damage_taken(self) -> float | None:
        return self._per10(self.damage_taken)

    @classmethod
    def from_mode(cls, mode: Any) -> "NormalizedModeStats":
        if mode is None:
            return cls()
        hero_damage = getattr(mode, "hero_damage", None)
        if hero_damage is None:
            hero_damage = getattr(mode, "damage", None)
        play_time = getattr(mode, "play_time", None)
        if play_time is None:
            play_time = getattr(mode, "play_time_seconds", None)
        return cls(
            matches=_optional_int(getattr(mode, "matches", None)),
            effective_matches=_optional_float(getattr(mode, "effective_matches", None)),
            wins=_optional_int(getattr(mode, "wins", None)),
            kills=_optional_int(getattr(mode, "kills", None)),
            final_hits=_optional_int(getattr(mode, "final_hits", None)),
            solo_eliminations=_optional_int(getattr(mode, "solo_eliminations", None)),
            critical_eliminations=_optional_int(getattr(mode, "critical_eliminations", None)),
            main_attack_count=_optional_int(getattr(mode, "main_attack_count", None)),
            main_attack_hits=_optional_int(getattr(mode, "main_attack_hits", None)),
            deaths=_optional_int(getattr(mode, "deaths", None)),
            assists=_optional_int(getattr(mode, "assists", None)),
            hero_damage=_optional_int(hero_damage),
            heal=_optional_int(getattr(mode, "heal", None)),
            damage_taken=_optional_int(getattr(mode, "damage_taken", None)),
            play_time=_optional_float(play_time),
            mvp=_optional_int(getattr(mode, "mvp", None)),
            svp=_optional_int(getattr(mode, "svp", None)),
            dynamic_sum=_dynamic_dict(getattr(mode, "dynamic_sum", None)),
            dynamic_max=_dynamic_dict(getattr(mode, "dynamic_max", None)),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "NormalizedModeStats":
        if not isinstance(value, dict):
            return cls()
        return cls(
            matches=_optional_int(value.get("matches")),
            effective_matches=_optional_float(value.get("effective_matches")),
            wins=_optional_int(value.get("wins")),
            kills=_optional_int(value.get("kills")),
            final_hits=_optional_int(value.get("final_hits")),
            solo_eliminations=_optional_int(value.get("solo_eliminations")),
            critical_eliminations=_optional_int(value.get("critical_eliminations")),
            main_attack_count=_optional_int(value.get("main_attack_count")),
            main_attack_hits=_optional_int(value.get("main_attack_hits")),
            deaths=_optional_int(value.get("deaths")),
            assists=_optional_int(value.get("assists")),
            hero_damage=_optional_int(value.get("hero_damage")),
            heal=_optional_int(value.get("heal")),
            damage_taken=_optional_int(value.get("damage_taken")),
            play_time=_optional_float(value.get("play_time")),
            mvp=_optional_int(value.get("mvp")),
            svp=_optional_int(value.get("svp")),
            dynamic_sum=_dynamic_dict(value.get("dynamic_sum")),
            dynamic_max=_dynamic_dict(value.get("dynamic_max")),
        )

    def difference(self, previous: "NormalizedModeStats | None") -> "NormalizedModeStats":
        previous = previous or NormalizedModeStats()
        values: dict[str, int | float | None] = {}
        for field_name in self.__dataclass_fields__:
            current = getattr(self, field_name)
            old = getattr(previous, field_name)
            if field_name == "dynamic_sum":
                values[field_name] = _difference_dynamic(current, old)
                continue
            if field_name == "dynamic_max":
                values[field_name] = _dynamic_dict(current)
                continue
            if current is None:
                values[field_name] = None
            elif field_name != "matches" and previous.matches and old is None:
                # A cumulative snapshot with an omitted metric cannot produce
                # a trustworthy delta for a predecessor that had games.
                values[field_name] = None
            elif old is None:
                values[field_name] = max(0, current)
            else:
                values[field_name] = max(0, current - old)
        return type(self)(**values)

    def add(self, other: "NormalizedModeStats") -> "NormalizedModeStats":
        values: dict[str, int | float | None] = {}
        for field_name in self.__dataclass_fields__:
            current = getattr(self, field_name)
            other_value = getattr(other, field_name)
            if field_name == "dynamic_sum":
                values[field_name] = _add_dynamic(current, other_value)
                continue
            if field_name == "dynamic_max":
                values[field_name] = _max_dynamic(current, other_value)
                continue
            if field_name != "matches" and (
                (self.matches and current is None)
                or (other.matches and other_value is None)
            ):
                values[field_name] = None
                continue
            values[field_name] = _sum_optional(
                current, other_value
            )
        return type(self)(**values)

    @property
    def win_rate(self) -> float | None:
        if self.matches and self.wins is not None:
            return self.wins * 100 / self.matches
        return None


@dataclass(frozen=True, slots=True)
class AnalysisScope:
    """Explicit career or one-season scope for player analysis."""

    kind: str
    season_code: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"career", "season"}:
            raise ValueError("分析范围必须是 career 或 season")
        if self.kind == "career" and self.season_code is not None:
            raise ValueError("生涯分析不能携带赛季编码")
        if self.kind == "season" and not str(self.season_code or "").strip():
            raise ValueError("单赛季分析必须提供赛季编码")

    @classmethod
    def career(cls) -> "AnalysisScope":
        return cls("career")

    @classmethod
    def season(cls, season_code: str | int) -> "AnalysisScope":
        return cls("season", str(season_code).strip())

    @property
    def key(self) -> str:
        return "career" if self.kind == "career" else f"season:{self.season_code}"


def analysis_scope_label(scope: AnalysisScope | None) -> str:
    """Return the only user-facing label allowed for an analysis scope."""

    if scope is None or scope.kind == "career":
        return "生涯"
    try:
        return season_identity_from_cn_code(scope.season_code).canonical_name
    except (TypeError, ValueError):
        return f"S{scope.season_code}"


@dataclass(slots=True)
class HeroSeasonPerformance:
    """One hero's competitive performance in one historical season."""

    season_code: str
    season_label: str
    rank_level: int | None
    rank_label: str | None
    meta_rank_code: str
    meta_rank_label: str
    quick_matches: int
    competitive_matches: int
    competitive_wins: int | None
    competitive_win_rate: float | None
    meta_matches: int | None
    meta_win_rate: float | None
    meta_pick_rate: float | None
    meta_ban_rate: float | None
    raw_delta: float | None
    rank_fallback: bool
    meta_available: bool


@dataclass(slots=True)
class CareerHeroSignature:
    """Aggregated, explainable career signature for one hero."""

    hero_id: str
    hero_name: str
    total_matches: int
    quick_matches: int
    competitive_matches: int
    competitive_wins: int | None
    usage_share: float
    actual_win_rate: float | None
    expected_meta_win_rate: float | None
    raw_delta: float | None
    adjusted_delta: float | None
    active_seasons: int
    competitive_seasons: int
    comparable_seasons: int
    effective_seasons: int
    positive_seasons: int
    stability: float | None
    comparable_matches: int
    meta_coverage: float
    rank_specific_coverage: float
    confidence: str
    classification: str
    tags: tuple[str, ...]
    seasons: tuple[HeroSeasonPerformance, ...]
    sick_score: float = 0.0
    quick_wins: int | None = None
    quick_win_rate: float | None = None
    play_index: float = 0.0
    weakness_index: float = 0.0
    meta_disadvantage: float | None = None
    personal_competitive_disadvantage: float | None = None
    personal_quick_disadvantage: float | None = None
    scope: AnalysisScope | None = None
    quick_stats: NormalizedModeStats | None = None
    competitive_stats: NormalizedModeStats | None = None
    meta_delta: float | None = None
    adjusted_meta_delta: float | None = None
    personal_competitive_delta: float | None = None
    personal_quick_delta: float | None = None
    performance_index: float = 0.0
    signature_score: float = 0.0
    sickness_score: float = 0.0
    raw_meta_delta: float | None = None
    raw_personal_competitive_delta: float | None = None
    adjusted_personal_competitive_delta: float | None = None
    raw_personal_quick_delta: float | None = None
    adjusted_personal_quick_delta: float | None = None
    evidence_factor: float = 1.0
    status: str = "常用英雄"
    is_analysis_eligible: bool = False
    is_signature_candidate: bool = False
    is_sickness_candidate: bool = False
    comparable_competitive_matches: int = 0
    comparable_competitive_wins: int = 0
    comparable_competitive_win_rate: float | None = None
    # V2 is additive: old fields remain populated for v1/shadow consumers.
    rating: "HeroRatingResult | None" = None


@dataclass(slots=True)
class PlayerSignatureProfile:
    """Stable ViewModel for cross-season player-specialty analysis."""

    uid: str
    player_name: str
    first_season: str
    latest_season: str
    analyzed_seasons: tuple[str, ...]
    total_matches: int
    competitive_matches: int
    meta_coverage: float
    signature_heroes: tuple[CareerHeroSignature, ...]
    favorite_hero: CareerHeroSignature | None
    partial: bool
    failed_seasons: tuple[str, ...]
    meta_source: str = "RivalsMeta"
    meta_source_timestamp: str | None = None
    meta_stale: bool = False
    meta_available: bool = True
    sick_heroes: tuple[CareerHeroSignature, ...] = ()
    scope: AnalysisScope = field(default_factory=AnalysisScope.career)
    heroes: tuple[CareerHeroSignature, ...] = ()
    rating_version: str = "shadow"


class HeroPerformanceAnalysis(CareerHeroSignature):
    """Public name for the unified Player × Hero analysis ViewModel."""


class PlayerCareerAnalysis(PlayerSignatureProfile):
    """Unified player analysis profile consumed by all personal views."""


@dataclass(slots=True)
class HeroPoolAnalysis:
    """Locally derived structure/quality view over one career analysis."""

    uid: str
    player_name: str
    scope: AnalysisScope
    total_matches: int
    active_heroes: int
    core_heroes: tuple[CareerHeroSignature, ...]
    top1_share: float
    top3_share: float
    effective_pool_width: float
    vanguard_share: float
    duelist_share: float
    strategist_share: float
    weighted_performance: float | None
    positive_usage_share: float
    negative_usage_share: float
    structure_tags: tuple[str, ...]
    meta_available: bool = True
    meta_stale: bool = False
    style_shares: dict[str, float] = field(default_factory=dict)
    profile_shares: dict[str, float] = field(default_factory=dict)
    tactical_tags: tuple[str, ...] = ()


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dynamic_dict(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, item in value.items():
        try:
            result[str(key)] = float(item)
        except (TypeError, ValueError):
            continue
    return result


def _difference_dynamic(current: Any, previous: Any) -> dict[str, float]:
    current_values = _dynamic_dict(current)
    previous_values = _dynamic_dict(previous)
    return {
        key: max(0.0, value - previous_values.get(key, 0.0))
        for key, value in current_values.items()
    }


def _add_dynamic(first: Any, second: Any) -> dict[str, float]:
    result = _dynamic_dict(first)
    for key, value in _dynamic_dict(second).items():
        result[key] = result.get(key, 0.0) + value
    return result


def _max_dynamic(first: Any, second: Any) -> dict[str, float]:
    result = _dynamic_dict(first)
    for key, value in _dynamic_dict(second).items():
        result[key] = max(result.get(key, value), value)
    return result


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum_optional(*values: int | float | None) -> int | float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None
