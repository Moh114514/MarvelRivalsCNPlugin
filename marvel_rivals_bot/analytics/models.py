"""Stable ViewModels for player and global Meta comparisons."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..meta.models import HeroMetaOverview


@dataclass(slots=True)
class PlayerHeroMetaComparison:
    """One player's hero result next to the same-rank global Meta result."""

    hero_id: str
    hero_name: str
    personal_matches: int
    personal_wins: int | None
    personal_win_rate: float | None
    meta_matches: int | None
    meta_win_rate: float | None
    meta_pick_rate: float | None
    meta_ban_rate: float | None
    win_rate_delta: float | None
    total_matches: int = 0
    quick_matches: int = 0
    ranked_matches: int = 0
    ranked_wins: int | None = None
    ranked_win_rate: float | None = None
    ranked_share: float | None = None


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
    minimum_ranked_matches: int = 10
