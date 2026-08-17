"""Stable ViewModels for player and global Meta comparisons."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..meta.models import HeroMetaOverview


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
    total_matches: int = 0
    quick_matches: int = 0
    ranked_matches: int = 0
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
        if self.competitive_matches is None:
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
        self.ranked_matches = self.competitive_matches or 0
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
    minimum_ranked_matches: int = 10

    @property
    def minimum_competitive_matches(self) -> int:
        return self.minimum_ranked_matches
