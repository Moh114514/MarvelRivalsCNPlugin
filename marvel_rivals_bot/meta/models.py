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
