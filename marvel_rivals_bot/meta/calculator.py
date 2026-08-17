from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from ..reference.heroes import get_hero_name
from .models import (
    HeroMetaResult,
    RawBanRankBucket,
    RawBanStat,
    RawHeroMetaStat,
    RawHeroRankBucket,
)
from ..reference.ranks import normalize_rank, rank_codes, rank_label


@dataclass(slots=True)
class _HeroCounts:
    matches: int = 0
    wins: int = 0
    wr_matches: int = 0
    wr_wins: int = 0
    mirror_matches: int = 0

    def add(self, row: RawHeroMetaStat) -> None:
        self.matches += row.matches
        self.wins += row.wins
        self.wr_matches += row.wr_matches
        self.wr_wins += row.wr_wins
        self.mirror_matches += row.mirror_matches


T = TypeVar("T")


def _selected(buckets: Iterable[T], rank: str | int, attr: str = "rank_code") -> list[T]:
    selected = set(rank_codes(rank))
    return [bucket for bucket in buckets if str(getattr(bucket, attr)) in selected]


def aggregate_hero_stats(
    buckets: Sequence[RawHeroRankBucket], rank: str | int = "all"
) -> list[RawHeroMetaStat]:
    """Aggregate raw hero counts for one rank, a composite, or all ranks."""

    counts: dict[int | None, _HeroCounts] = defaultdict(_HeroCounts)
    for bucket in _selected(buckets, rank):
        for row in bucket.heroes:
            counts[row.hero_id].add(row)
    return [
        RawHeroMetaStat(
            hero_id=hero_id,
            matches=value.matches,
            wins=value.wins,
            wr_matches=value.wr_matches,
            wr_wins=value.wr_wins,
            mirror_matches=value.mirror_matches,
        )
        for hero_id, value in counts.items()
    ]


def aggregate_ban_stats(
    buckets: Sequence[RawBanRankBucket] | None, rank: str | int = "all"
) -> tuple[list[RawBanStat], bool]:
    """Aggregate ban counts and report whether usable selected data exists.

    RivalsMeta currently omits the Bronze and Silver ban buckets. Its explicit
    All Ranks response is therefore still usable when the available ban
    buckets are aggregated, while a single rank or composite query remains
    unavailable unless every requested bucket is present.
    """

    if buckets is None:
        return [], False
    counts: dict[int | None, int] = defaultdict(int)
    rank_key = normalize_rank(rank)
    selected_codes = set(rank_codes(rank_key))
    selected_buckets = _selected(buckets, rank_key)
    for bucket in selected_buckets:
        for row in bucket.bans:
            counts[row.hero_id] += row.bans
    available_codes = {str(bucket.rank_code) for bucket in buckets}
    complete = bool(selected_buckets) and (
        rank_key == "all" or selected_codes.issubset(available_codes)
    )
    return [RawBanStat(hero_id=hero_id, bans=bans) for hero_id, bans in counts.items()], complete


def calc_win_rate(wr_wins: int, wr_matches: int) -> float:
    if wr_matches <= 0:
        return 0.0
    return wr_wins / wr_matches * 100


def calc_pick_rate(matches: int, total_matches: int) -> float:
    pick_base = total_matches / 6 if total_matches > 0 else 0
    return matches / pick_base * 100 if pick_base else 0.0


def calc_ban_rate(bans: int, total_bans: int) -> float:
    ban_base = total_bans / 2 if total_bans > 0 else 0
    return bans / ban_base * 100 if ban_base else 0.0


def calculate_hero_results(
    hero_buckets: Sequence[RawHeroRankBucket],
    ban_buckets: Sequence[RawBanRankBucket] | None,
    *,
    rank: str | int = "all",
    sort_by: str = "win_rate",
    hero_name_resolver: Callable[[int], str] | None = None,
) -> list[HeroMetaResult]:
    """Calculate display-ready hero statistics from raw rank buckets.

    Denominators intentionally use every selected raw row before invalid hero IDs
    are removed from the display results.
    """

    hero_rows = aggregate_hero_stats(hero_buckets, rank)
    ban_rows, has_bans_bucket = aggregate_ban_stats(ban_buckets, rank)
    selected_hero_buckets = _selected(hero_buckets, rank)
    total_matches = sum(row.matches for bucket in selected_hero_buckets for row in bucket.heroes)
    total_bans = (
        sum(row.bans for bucket in _selected(ban_buckets or [], rank) for row in bucket.bans)
        if has_bans_bucket
        else 0
    )
    ban_by_hero = {row.hero_id: row.bans for row in ban_rows}
    resolve_name = hero_name_resolver or (lambda hero_id: get_hero_name(hero_id, f"未知英雄（{hero_id}）"))

    results: list[HeroMetaResult] = []
    for row in hero_rows:
        if row.hero_id is None or row.hero_id == 0:
            continue
        bans = ban_by_hero.get(row.hero_id, 0) if has_bans_bucket else None
        results.append(
            HeroMetaResult(
                hero_id=row.hero_id,
                hero_name=resolve_name(row.hero_id),
                matches=row.matches,
                wins=row.wins,
                wr_matches=row.wr_matches,
                wr_wins=row.wr_wins,
                mirror_matches=row.mirror_matches,
                bans=bans,
                win_rate=calc_win_rate(row.wr_wins, row.wr_matches),
                pick_rate=calc_pick_rate(row.matches, total_matches),
                ban_rate=calc_ban_rate(bans, total_bans) if bans is not None else None,
            )
        )

    key = _sort_key(sort_by)
    if key == "ban_rate":
        available = sorted((item for item in results if item.ban_rate is not None), key=lambda item: item.ban_rate, reverse=True)
        unavailable = [item for item in results if item.ban_rate is None]
        return available + unavailable
    return sorted(results, key=lambda item: getattr(item, key), reverse=True)


def _sort_key(value: str) -> str:
    aliases = {
        "胜率": "win_rate",
        "选取率": "pick_rate",
        "选取": "pick_rate",
        "pick": "pick_rate",
        "ban": "ban_rate",
        "ban率": "ban_rate",
        "ban rate": "ban_rate",
        "场次": "matches",
        "matches": "matches",
        "胜率": "win_rate",
    }
    key = aliases.get(str(value).strip().lower(), str(value).strip().lower())
    if key not in {"win_rate", "pick_rate", "ban_rate", "matches"}:
        raise ValueError(f"未知排序字段：{value}")
    return key


# Explicit aliases keep the functions easy to discover without coupling them to
# a future MetaService implementation.
calculate_hero_meta = calculate_hero_results
build_hero_meta_results = calculate_hero_results


def aggregate_rank_buckets(
    hero_buckets: Sequence[RawHeroRankBucket],
    ban_buckets: Sequence[RawBanRankBucket] | None = None,
    rank: str | int = "all",
) -> tuple[list[RawHeroMetaStat], list[RawBanStat], bool]:
    """Return aggregated raw counters and whether a matching ban bucket exists."""

    hero_rows = aggregate_hero_stats(hero_buckets, rank)
    ban_rows, has_bans = aggregate_ban_stats(ban_buckets, rank)
    return hero_rows, ban_rows, has_bans


__all__ = [
    "aggregate_ban_stats",
    "aggregate_rank_buckets",
    "aggregate_hero_stats",
    "build_hero_meta_results",
    "calc_win_rate",
    "calc_pick_rate",
    "calc_ban_rate",
    "calculate_hero_meta",
    "calculate_hero_results",
    "normalize_rank",
    "rank_label",
]
