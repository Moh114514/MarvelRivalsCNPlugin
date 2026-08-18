from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class RawHeroMetaStat:
    hero_id: int | None
    matches: int
    wins: int
    wr_matches: int
    wr_wins: int
    mirror_matches: int


@dataclass(slots=True)
class RawHeroRankBucket:
    rank_code: str
    heroes: list[RawHeroMetaStat]


@dataclass(slots=True)
class RawBanStat:
    hero_id: int | None
    bans: int


@dataclass(slots=True)
class RawBanRankBucket:
    rank_code: str
    bans: list[RawBanStat]


@dataclass(slots=True)
class RawHeroMetaPayload:
    season: int
    heroes: list[RawHeroRankBucket]
    bans: list[RawBanRankBucket] | None
    source_timestamp: int | float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    fetched_at: datetime | None = None
    stale: bool = False
    source: str = "RivalsMeta"


@dataclass(slots=True)
class HeroMetaResult:
    hero_id: int
    hero_name: str
    matches: int
    wins: int
    wr_matches: int
    wr_wins: int
    mirror_matches: int
    bans: int | None
    win_rate: float
    pick_rate: float
    ban_rate: float | None


@dataclass(slots=True)
class HeroMetaBoard:
    season_code: str
    season_label: str
    rank_key: str
    rank_label: str
    sort_by: str
    heroes: list[HeroMetaResult]
    source: str
    source_timestamp: datetime | None
    fetched_at: datetime
    stale: bool = False


@dataclass(slots=True)
class HeroMetaOverview:
    """Top heroes for each supported environment metric."""

    season_code: str
    season_label: str
    rank_key: str
    rank_label: str
    win_rate: list[HeroMetaResult]
    pick_rate: list[HeroMetaResult]
    ban_rate: list[HeroMetaResult]
    source: str
    source_timestamp: datetime | None
    fetched_at: datetime
    stale: bool = False


@dataclass(slots=True)
class HeroMetaSegment:
    """One hero's calculated statistics in one canonical Meta rank."""

    rank_code: str
    rank_label: str
    result: HeroMetaResult | None


@dataclass(slots=True)
class HeroMetaSegments:
    """A complete rank-by-rank view for one hero and one season."""

    hero_id: int
    hero_name: str
    season_code: str
    season_label: str
    segments: list[HeroMetaSegment]
    source: str
    source_timestamp: datetime | None
    fetched_at: datetime
    stale: bool = False


@dataclass(slots=True)
class HeroMetaComparison:
    """Two heroes calculated from the same season/rank context."""

    season_code: str
    season_label: str
    rank_key: str
    rank_label: str
    left: HeroMetaResult
    right: HeroMetaResult
    source: str
    source_timestamp: datetime | None
    fetched_at: datetime
    stale: bool = False


@dataclass(slots=True)
class HeroRankPoint:
    """One hero's calculated Meta snapshot in a historical season."""

    season_code: str
    season_label: str
    result: HeroMetaResult | None
    win_rate_delta: float | None = None
    pick_rate_delta: float | None = None
    ban_rate_delta: float | None = None


@dataclass(slots=True)
class HeroRankSeries:
    """A cross-season series for one hero and one rank context."""

    hero_id: int
    hero_name: str
    rank_key: str
    rank_label: str
    points: list[HeroRankPoint]
    source: str
    source_timestamps: tuple[datetime | None, ...]
    source_timestamp: datetime | None
    fetched_at: datetime
    stale: bool = False


@dataclass(slots=True)
class SeasonDelta:
    """Metric deltas between two season snapshots for one hero."""

    hero_id: int
    hero_name: str
    previous: HeroMetaResult
    current: HeroMetaResult
    win_rate_delta: float | None
    pick_rate_delta: float | None
    ban_rate_delta: float | None


@dataclass(slots=True)
class HeroMetaVersionChanges:
    """Ranked metric changes between two Meta season snapshots."""

    previous_season_code: str
    previous_season_label: str
    current_season_code: str
    current_season_label: str
    rank_key: str
    rank_label: str
    win_rate_up: list[SeasonDelta]
    win_rate_down: list[SeasonDelta]
    pick_rate_up: list[SeasonDelta]
    pick_rate_down: list[SeasonDelta]
    ban_rate_up: list[SeasonDelta]
    ban_rate_down: list[SeasonDelta]
    source: str
    source_timestamps: tuple[datetime | None, ...]
    source_timestamp: datetime | None
    fetched_at: datetime
    stale: bool = False


@dataclass(slots=True)
class HeroMetaInsight:
    """One transparent historical or distribution-based insight."""

    result: HeroMetaResult
    previous: HeroMetaResult | None = None
    win_rate_delta: float | None = None
    pick_rate_delta: float | None = None
    ban_rate_delta: float | None = None
    rank_code: str | None = None
    rank_label: str | None = None


@dataclass(slots=True)
class HeroMetaInsights:
    """A filtered insight board with its user-facing rule."""

    insight_type: str
    season_code: str
    season_label: str
    previous_season_code: str | None
    previous_season_label: str | None
    rank_key: str
    rank_label: str
    rule: str
    items: list[HeroMetaInsight]
    source: str
    source_timestamps: tuple[datetime | None, ...]
    source_timestamp: datetime | None
    fetched_at: datetime
    stale: bool = False


@dataclass(slots=True)
class RankMonster:
    """One hero that passes the rank-specialist filter."""

    rank_code: str
    rank_label: str
    result: HeroMetaResult
    win_rate_delta: float | None


@dataclass(slots=True)
class RankSegment:
    """All qualifying heroes for one rank, kept in game rank order."""

    rank_code: str
    rank_label: str
    items: list[RankMonster]


@dataclass(slots=True)
class RankMonsterBoard:
    """Rank-specialist filter results grouped by rank, not a leaderboard."""

    season_code: str
    season_label: str
    rule: str
    segments: list[RankSegment]
    source: str
    source_timestamps: tuple[datetime | None, ...]
    source_timestamp: datetime | None
    fetched_at: datetime
    stale: bool = False

    @property
    def items(self) -> list[RankMonster]:
        """Compatibility view for callers that used the old flat board."""

        return [item for segment in self.segments for item in segment.items]


# Names used by earlier design notes remain available without introducing a
# second set of ViewModels.
HeroMetaTrend = HeroRankSeries
HeroMetaDelta = SeasonDelta
