"""Application service for global hero Meta data."""

from __future__ import annotations

import logging
import time
import asyncio
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from collections.abc import Sequence
from statistics import median
from typing import Any

from ..datasource.base import DataSourceError
from ..reference.heroes import get_hero_id, get_hero_name
from ..reference.ranks import get_rank_label, normalize_rank, rank_codes
from ..reference.seasons import (
    get_season_identity,
    season_identity_from_rivalsmeta_code,
)
from .cache import CacheRecord, MetaDiskCache
from .calculator import _sort_key, calculate_hero_results, sort_hero_results
from .errors import MetaCacheError, MetaDataSourceError, MetaQueryError
from .models import (
    HeroMetaBoard,
    HeroMetaComparison,
    HeroMetaOverview,
    HeroMetaRoleBoard,
    HeroMetaRoleBoards,
    HeroMetaResult,
    HeroMetaSegment,
    HeroMetaSegments,
    HeroMetaInsight,
    HeroMetaInsights,
    HeroMetaVersionChanges,
    HeroRankPoint,
    HeroRankSeries,
    RankMonster,
    RankMonsterBoard,
    RankSegment,
    SeasonDelta,
    RawHeroMetaPayload,
    RankingRange,
)


logger = logging.getLogger(__name__)


def _slice_ranking(
    results: list[HeroMetaResult],
    ranking_range: RankingRange | None,
    limit: int | None,
) -> list[HeroMetaResult]:
    if ranking_range is not None:
        if ranking_range.from_tail is not None:
            return results[-ranking_range.from_tail:]
        start = max(1, ranking_range.start or 1)
        end = ranking_range.end
        return results[start - 1:end] if end is not None else results[start - 1:]
    if limit is None:
        return results
    return results[: max(0, int(limit))]


def _display_window(
    total_count: int,
    ranking_range: RankingRange | None,
    limit: int | None,
) -> tuple[int | None, int | None]:
    if total_count <= 0:
        return None, None
    if ranking_range is not None and ranking_range.from_tail is not None:
        start = max(1, total_count - ranking_range.from_tail + 1)
        return start, total_count
    start = ranking_range.start if ranking_range is not None and ranking_range.start is not None else 1
    requested_end = ranking_range.end if ranking_range is not None else limit
    end = total_count if requested_end is None else min(total_count, requested_end)
    return start, max(start, end)


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 100_000_000_000:
            number /= 1000
        try:
            return datetime.fromtimestamp(number, timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return _as_datetime(float(text))
        except ValueError:
            return None


@dataclass(slots=True)
class _MemoryRecord:
    loaded_at: float
    payload: RawHeroMetaPayload


class MetaService:
    """Coordinate source, cache, calculations, and stable Meta ViewModels."""

    def __init__(
        self,
        source,
        *,
        cache_root,
        fresh_seconds: float = 600,
        stale_seconds: float = 86400,
        default_season: str = "19",
        cache: MetaDiskCache | None = None,
        request_semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self.source = source
        self.default_season = str(default_season).strip() or "19"
        self.cache = cache or MetaDiskCache(
            cache_root,
            fresh_seconds=fresh_seconds,
            stale_seconds=stale_seconds,
        )
        self.fresh_seconds = max(0.0, float(fresh_seconds))
        self._memory: dict[str, _MemoryRecord] = {}
        self._request_semaphore = request_semaphore or asyncio.Semaphore(8)
        self._inflight: dict[str, asyncio.Task[RawHeroMetaPayload]] = {}

    def default_historical_seasons(self, count: int = 4) -> tuple[str, ...]:
        """Return the latest known season names in chronological order."""

        try:
            size = int(count)
        except (TypeError, ValueError) as exc:
            raise MetaQueryError("历史赛季数量必须是正整数") from exc
        if size < 1:
            raise MetaQueryError("历史赛季数量必须是正整数")
        current = int(self.season_code())
        first = max(1, current - size + 1)
        return tuple(
            season_identity_from_rivalsmeta_code(code).canonical_name
            for code in range(first, current + 1)
        )

    def previous_season(self, season: str | None = None) -> str:
        """Return the canonical name immediately before a requested season."""

        code = int(self.season_code(season))
        if code <= 1:
            raise MetaQueryError("S0 没有更早的可比较赛季")
        return season_identity_from_rivalsmeta_code(code - 1).canonical_name

    async def _load_historical_payloads(
        self,
        seasons: Sequence[str] | None,
    ) -> list[RawHeroMetaPayload]:
        codes = self._historical_codes(seasons)
        return list(await asyncio.gather(*(self.get_raw_hero_meta(code) for code in codes)))

    def _historical_codes(self, seasons: Sequence[str] | None) -> list[str]:
        requested = list(seasons or self.default_historical_seasons())
        if not requested:
            raise MetaQueryError("至少需要一个赛季")
        codes: list[str] = []
        for season in requested:
            code = self.season_code(season)
            if code not in codes:
                codes.append(code)
        return codes

    async def _load_historical_payloads_partial(
        self,
        seasons: Sequence[str] | None,
    ) -> tuple[list[str], list[RawHeroMetaPayload | None]]:
        """Load a trend as a partial series while keeping strict callers strict."""

        codes = self._historical_codes(seasons)
        loaded = await asyncio.gather(
            *(self.get_raw_hero_meta(code) for code in codes),
            return_exceptions=True,
        )
        payloads: list[RawHeroMetaPayload | None] = []
        for code, value in zip(codes, loaded):
            if isinstance(value, MetaDataSourceError):
                logger.warning(
                    "Meta source=%s season=%s trend_partial_failure=%s",
                    getattr(self.source, "SOURCE_NAME", type(self.source).__name__),
                    code,
                    type(value).__name__,
                )
                payloads.append(None)
                continue
            if isinstance(value, Exception):
                raise value
            payloads.append(value)
        if not any(payloads):
            first_error = next(
                (value for value in loaded if isinstance(value, MetaDataSourceError)),
                None,
            )
            if first_error is not None:
                raise first_error
            raise MetaQueryError("没有可用的历史赛季数据")
        return codes, payloads

    @staticmethod
    def _history_context(
        payloads: Sequence[RawHeroMetaPayload],
    ) -> tuple[str, tuple[datetime | None, ...], datetime, bool]:
        if not payloads:
            raise MetaQueryError("没有可用的历史赛季数据")
        timestamps = tuple(_as_datetime(payload.source_timestamp) for payload in payloads)
        fetched_values = [payload.fetched_at for payload in payloads if payload.fetched_at is not None]
        fetched_at = max(fetched_values) if fetched_values else datetime.now(timezone.utc)
        return payloads[-1].source, timestamps, fetched_at, any(payload.stale for payload in payloads)

    @staticmethod
    def _latest_timestamp(timestamps: Sequence[datetime | None]) -> datetime | None:
        valid = [value for value in timestamps if value is not None]
        if not valid:
            return None
        return max(
            valid,
            key=lambda value: (
                value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
            ).timestamp(),
        )

    @staticmethod
    def _results_by_hero(
        payload: RawHeroMetaPayload,
        rank: str,
        *,
        sort_by: str = "matches",
    ) -> dict[int, HeroMetaResult]:
        return {
            result.hero_id: result
            for result in calculate_hero_results(
                payload.heroes,
                payload.bans,
                rank=rank,
                sort_by=sort_by,
            )
        }

    @staticmethod
    def _delta(current: float | None, previous: float | None) -> float | None:
        if current is None or previous is None:
            return None
        return current - previous

    @staticmethod
    def _rank_deltas(
        deltas: Sequence[SeasonDelta],
        metric: str,
        *,
        rising: bool,
        limit: int,
    ) -> list[SeasonDelta]:
        available = [item for item in deltas if getattr(item, metric) is not None]
        if rising:
            available = [item for item in available if getattr(item, metric) > 0]
            available.sort(key=lambda item: (getattr(item, metric), item.current.matches), reverse=True)
        else:
            available = [item for item in available if getattr(item, metric) < 0]
            available.sort(key=lambda item: (getattr(item, metric), -item.current.matches))
        return available[: max(0, int(limit))]

    @staticmethod
    def _positive_matches(value: Any) -> int:
        try:
            matches = int(value)
        except (TypeError, ValueError) as exc:
            raise MetaQueryError("最低样本场次必须是正整数") from exc
        if matches < 1:
            raise MetaQueryError("最低样本场次必须是正整数")
        return matches

    def season_code(self, season: str | None = None) -> str:
        value = str(season or "").strip()
        try:
            if not value:
                return get_season_identity(self.default_season, "rivalsmeta").for_provider("rivalsmeta")
            # Raw numeric codes are useful for internal/debug calls, while
            # command handlers pass user-facing names through this boundary.
            return get_season_identity(value).for_provider("rivalsmeta")
        except (DataSourceError, TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc

    async def get_raw_hero_meta(self, season: str | None = None) -> RawHeroMetaPayload:
        season_code = self.season_code(season)
        return await self._singleflight(
            f"meta:{season_code}",
            lambda: self._get_raw_hero_meta(season_code),
        )

    async def _get_raw_hero_meta(self, season_code: str) -> RawHeroMetaPayload:
        memory = self._memory.get(season_code)
        if memory and self.fresh_seconds > 0 and time.monotonic() - memory.loaded_at < self.fresh_seconds:
            logger.info("Meta source=%s season=%s cache=memory_fresh", memory.payload.source, season_code)
            return memory.payload
        if memory and self.fresh_seconds <= 0:
            self._memory.pop(season_code, None)

        stale_record = self.cache.load(season_code)
        if stale_record is not None and not stale_record.stale:
            try:
                payload = self._from_cache_record(stale_record)
            except MetaDataSourceError as cache_error:
                logger.warning(
                    "Meta source=%s season=%s cache=invalid_payload error=%s",
                    stale_record.source,
                    season_code,
                    type(cache_error).__name__,
                )
                stale_record = None
            else:
                self._memory[season_code] = _MemoryRecord(time.monotonic(), payload)
                logger.info("Meta source=%s season=%s cache=disk_fresh", payload.source, season_code)
                return payload

        try:
            payload = await self._request(lambda: self.source.get_hero_stats(season_code))
        except MetaDataSourceError as remote_error:
            if stale_record is not None:
                try:
                    payload = self._from_cache_record(stale_record)
                    logger.warning(
                        "Meta source=%s season=%s cache=stale_fallback",
                        payload.source,
                        season_code,
                    )
                    return payload
                except MetaDataSourceError as cache_error:
                    logger.warning(
                        "Meta source=%s season=%s cache=invalid_payload error=%s",
                        stale_record.source,
                        season_code,
                        type(cache_error).__name__,
                    )
            logger.warning(
                "Meta source=%s season=%s remote_failure=%s cache=stale_unavailable",
                getattr(self.source, "SOURCE_NAME", type(self.source).__name__),
                season_code,
                type(remote_error).__name__,
            )
            raise remote_error

        fetched_at = payload.fetched_at or datetime.now(timezone.utc)
        payload.fetched_at = fetched_at
        payload.stale = False
        raw = self._raw_payload(payload)
        try:
            self.cache.save(
                season_code,
                raw,
                payload.source,
                source_timestamp=payload.source_timestamp,
                fetched_at=fetched_at,
            )
        except MetaCacheError:
            # Cache is an optimization; a valid upstream response remains
            # usable when the runtime data directory is temporarily read-only.
            logger.warning(
                "Meta source=%s season=%s cache=write_failure",
                payload.source,
                season_code,
            )
        self._memory[season_code] = _MemoryRecord(time.monotonic(), payload)
        return payload

    async def _request(self, operation):
        async with self._request_semaphore:
            return await operation()

    async def _singleflight(self, key: str, factory):
        task = self._inflight.get(key)
        if task is None:
            task_holder: dict[str, asyncio.Task[RawHeroMetaPayload]] = {}

            async def run() -> RawHeroMetaPayload:
                try:
                    return await factory()
                finally:
                    current = task_holder.get("task")
                    if current is not None and self._inflight.get(key) is current:
                        self._inflight.pop(key, None)

            task = asyncio.create_task(run())
            task_holder["task"] = task
            self._inflight[key] = task
        return await asyncio.shield(task)

    async def get_hero_meta_board(
        self,
        *,
        season: str | None = None,
        rank: str = "all",
        sort_by: str = "win_rate",
        limit: int | None = 20,
        role: str | None = None,
        ranking_range: RankingRange | None = None,
        start: int | None = None,
        end: int | None = None,
        tail: int | None = None,
        group_by_role: bool = False,
    ) -> HeroMetaBoard:
        try:
            rank_key = normalize_rank(rank)
            sort_key = _sort_key(sort_by)
            self.season_code(season)
        except (TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc
        if role is not None and role not in {"vanguard", "duelist", "strategist"}:
            raise MetaQueryError(f"未知职责：{role}")
        if ranking_range is None and any(value is not None for value in (start, end, tail)):
            try:
                ranking_range = RankingRange(start=start, end=end, from_tail=tail)
            except ValueError as exc:
                raise MetaQueryError(str(exc)) from exc
        payload = await self.get_raw_hero_meta(season)
        results = calculate_hero_results(
            payload.heroes,
            payload.bans,
            rank=rank_key,
            sort_by=sort_key,
        )
        if role is not None:
            results = [item for item in results if item.role == role]
            results = sort_hero_results(results, sort_key)
        total_count = len(results)
        role_boards: list[HeroMetaRoleBoard] = []
        if group_by_role:
            for role_key, role_label in (("vanguard", "先锋"), ("duelist", "决斗"), ("strategist", "战略")):
                group = [item for item in results if item.role == role_key]
                group_total = len(group)
                group = _slice_ranking(group, ranking_range, limit)
                range_start, range_end = _display_window(group_total, ranking_range, limit)
                role_boards.append(
                    HeroMetaRoleBoard(
                        role_key,
                        role_label,
                        group,
                        range_start,
                        range_end,
                        group_total,
                    )
                )
            results = [item for group in role_boards for item in group.heroes]
        else:
            results = _slice_ranking(results, ranking_range, limit)
        range_start, range_end = _display_window(total_count, ranking_range, limit)
        return self._board(
            payload,
            rank_key,
            sort_key,
            results,
            role_filter=role,
            range_start=range_start,
            range_end=range_end,
            total_count=total_count,
            group_by_role=group_by_role,
            role_boards=role_boards,
        )

    async def get_hero_meta_role_boards(
        self,
        *,
        season: str | None = None,
        rank: str = "all",
        sort_by: str = "win_rate",
        limit: int | None = 10,
        ranking_range: RankingRange | None = None,
    ) -> HeroMetaRoleBoards:
        """Return one independently sliced ranking for each role."""

        board = await self.get_hero_meta_board(
            season=season,
            rank=rank,
            sort_by=sort_by,
            limit=limit,
            ranking_range=ranking_range,
            group_by_role=True,
        )
        return HeroMetaRoleBoards(
            season_code=board.season_code,
            season_label=board.season_label,
            rank_key=board.rank_key,
            rank_label=board.rank_label,
            sort_by=board.sort_by,
            roles=board.role_boards,
            source=board.source,
            source_timestamp=board.source_timestamp,
            fetched_at=board.fetched_at,
            stale=board.stale,
        )

    async def get_single_hero_meta(
        self,
        hero_name: str,
        *,
        season: str | None = None,
        rank: str = "all",
    ) -> HeroMetaResult:
        board = await self.get_single_hero_meta_board(hero_name, season=season, rank=rank)
        return board.heroes[0]

    async def get_hero_meta_overview(
        self,
        *,
        season: str | None = None,
        rank: str = "all",
        limit: int | None = 5,
    ) -> HeroMetaOverview:
        """Build one multi-metric overview from a single season payload."""

        board = await self.get_hero_meta_board(
            season=season,
            rank=rank,
            sort_by="win_rate",
            limit=None,
        )
        size = None if limit is None else max(0, int(limit))

        def top(metric: str) -> list[HeroMetaResult]:
            if metric == "ban_rate":
                ordered = sorted(
                    (item for item in board.heroes if item.ban_rate is not None),
                    key=lambda item: item.ban_rate,
                    reverse=True,
                )
                ordered.extend(item for item in board.heroes if item.ban_rate is None)
            else:
                ordered = sorted(
                    board.heroes,
                    key=lambda item: getattr(item, metric),
                    reverse=True,
                )
            return ordered if size is None else ordered[:size]

        return HeroMetaOverview(
            season_code=board.season_code,
            season_label=board.season_label,
            rank_key=board.rank_key,
            rank_label=board.rank_label,
            win_rate=top("win_rate"),
            pick_rate=top("pick_rate"),
            ban_rate=top("ban_rate"),
            source=board.source,
            source_timestamp=board.source_timestamp,
            fetched_at=board.fetched_at,
            stale=board.stale,
        )

    async def get_hero_meta_segments(
        self,
        hero_name: str,
        *,
        season: str | None = None,
    ) -> HeroMetaSegments:
        """Return one hero's metrics for every canonical Meta rank.

        The season payload is loaded once. Rank-specific aggregation remains
        local so this query never creates one remote request per rank.
        """

        try:
            hero_id = get_hero_id(hero_name)
        except (TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc

        payload = await self.get_raw_hero_meta(season)
        segments: list[HeroMetaSegment] = []
        found = False
        for rank_key in rank_codes("all"):
            results = calculate_hero_results(
                payload.heroes,
                payload.bans,
                rank=rank_key,
                sort_by="matches",
            )
            result = next((item for item in results if item.hero_id == hero_id), None)
            found = found or result is not None
            segments.append(
                HeroMetaSegment(
                    rank_code=rank_key,
                    rank_label=get_rank_label(rank_key),
                    result=result,
                )
            )
        if not found:
            raise MetaQueryError(f"没有找到英雄“{hero_name}”的环境数据")

        source_timestamp = _as_datetime(payload.source_timestamp)
        return HeroMetaSegments(
            hero_id=hero_id,
            hero_name=get_hero_name(hero_id),
            season_code=str(payload.season),
            season_label=season_identity_from_rivalsmeta_code(payload.season).label,
            segments=segments,
            source=payload.source,
            source_timestamp=source_timestamp,
            fetched_at=payload.fetched_at or datetime.now(timezone.utc),
            stale=payload.stale,
        )

    async def get_hero_meta_comparison(
        self,
        left_hero_name: str,
        right_hero_name: str,
        *,
        season: str | None = None,
        rank: str = "all",
    ) -> HeroMetaComparison:
        """Compare two heroes from one calculated rank context."""

        try:
            left_id = get_hero_id(left_hero_name)
            right_id = get_hero_id(right_hero_name)
            rank_key = normalize_rank(rank)
            self.season_code(season)
        except (TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc
        if left_id == right_id:
            raise MetaQueryError("英雄对比需要选择两个不同的英雄")

        payload = await self.get_raw_hero_meta(season)
        results = calculate_hero_results(
            payload.heroes,
            payload.bans,
            rank=rank_key,
            sort_by="matches",
        )
        by_id = {item.hero_id: item for item in results}
        left = by_id.get(left_id)
        right = by_id.get(right_id)
        missing = [
            name
            for name, result in ((left_hero_name, left), (right_hero_name, right))
            if result is None
        ]
        if missing:
            raise MetaQueryError(f"没有找到英雄“{missing[0]}”的环境数据")

        source_timestamp = _as_datetime(payload.source_timestamp)
        return HeroMetaComparison(
            season_code=str(payload.season),
            season_label=season_identity_from_rivalsmeta_code(payload.season).label,
            rank_key=rank_key,
            rank_label=get_rank_label(rank_key),
            left=left,
            right=right,
            source=payload.source,
            source_timestamp=source_timestamp,
            fetched_at=payload.fetched_at or datetime.now(timezone.utc),
            stale=payload.stale,
        )

    async def get_hero_meta_trend(
        self,
        hero_name: str,
        *,
        seasons: Sequence[str] | None = None,
        rank: str = "all",
    ) -> HeroRankSeries:
        """Return one hero's WR/Pick/Ban series across historical seasons."""

        try:
            hero_id = get_hero_id(hero_name)
            rank_key = normalize_rank(rank)
        except (TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc
        codes, payloads = await self._load_historical_payloads_partial(seasons)
        points: list[HeroRankPoint] = []
        found = False
        previous_result: HeroMetaResult | None = None
        for code, payload in zip(codes, payloads):
            result = self._results_by_hero(payload, rank_key).get(hero_id) if payload else None
            found = found or result is not None
            season_identity = season_identity_from_rivalsmeta_code(code)
            points.append(
                HeroRankPoint(
                    season_code=code,
                    season_label=season_identity.label,
                    result=result,
                    win_rate_delta=self._delta(
                        result.win_rate if result else None,
                        previous_result.win_rate if previous_result else None,
                    ),
                    pick_rate_delta=self._delta(
                        result.pick_rate if result else None,
                        previous_result.pick_rate if previous_result else None,
                    ),
                    ban_rate_delta=self._delta(
                        result.ban_rate if result else None,
                        previous_result.ban_rate if previous_result else None,
                    ),
                )
            )
            previous_result = result
        if not found:
            raise MetaQueryError(f"没有找到英雄“{hero_name}”的历史环境数据")
        usable_payloads = [payload for payload in payloads if payload is not None]
        source, usable_timestamps, fetched_at, stale = self._history_context(usable_payloads)
        timestamp_by_code = {
            str(payload.season): _as_datetime(payload.source_timestamp)
            for payload in usable_payloads
        }
        timestamps = tuple(timestamp_by_code.get(code) for code in codes)
        return HeroRankSeries(
            hero_id=hero_id,
            hero_name=get_hero_name(hero_id),
            rank_key=rank_key,
            rank_label=get_rank_label(rank_key),
            points=points,
            source=source,
            source_timestamps=timestamps,
            source_timestamp=self._latest_timestamp(timestamps),
            fetched_at=fetched_at,
            stale=stale,
        )

    async def get_meta_version_changes(
        self,
        previous_season: str,
        current_season: str,
        *,
        rank: str = "all",
        limit: int = 5,
    ) -> HeroMetaVersionChanges:
        """Compare two season snapshots without inventing a composite score."""

        try:
            rank_key = normalize_rank(rank)
            limit = max(0, int(limit))
        except (TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc
        previous_code = self.season_code(previous_season)
        current_code = self.season_code(current_season)
        if int(previous_code) >= int(current_code):
            raise MetaQueryError("版本变化请按旧赛季到新赛季指定，且两个赛季必须不同")
        payloads = await self._load_historical_payloads((previous_code, current_code))
        if len(payloads) != 2:
            raise MetaQueryError("版本变化需要两个不同的赛季")
        previous_payload, current_payload = payloads
        previous = self._results_by_hero(previous_payload, rank_key)
        current = self._results_by_hero(current_payload, rank_key)
        deltas = [
            SeasonDelta(
                hero_id=hero_id,
                hero_name=current_result.hero_name,
                previous=previous_result,
                current=current_result,
                win_rate_delta=self._delta(current_result.win_rate, previous_result.win_rate),
                pick_rate_delta=self._delta(current_result.pick_rate, previous_result.pick_rate),
                ban_rate_delta=self._delta(current_result.ban_rate, previous_result.ban_rate),
            )
            for hero_id in sorted(previous.keys() & current.keys())
            for previous_result, current_result in [(previous[hero_id], current[hero_id])]
        ]
        source, timestamps, fetched_at, stale = self._history_context(payloads)
        previous_identity = season_identity_from_rivalsmeta_code(previous_payload.season)
        current_identity = season_identity_from_rivalsmeta_code(current_payload.season)
        return HeroMetaVersionChanges(
            previous_season_code=str(previous_payload.season),
            previous_season_label=previous_identity.label,
            current_season_code=str(current_payload.season),
            current_season_label=current_identity.label,
            rank_key=rank_key,
            rank_label=get_rank_label(rank_key),
            win_rate_up=self._rank_deltas(deltas, "win_rate_delta", rising=True, limit=limit),
            win_rate_down=self._rank_deltas(deltas, "win_rate_delta", rising=False, limit=limit),
            pick_rate_up=self._rank_deltas(deltas, "pick_rate_delta", rising=True, limit=limit),
            pick_rate_down=self._rank_deltas(deltas, "pick_rate_delta", rising=False, limit=limit),
            ban_rate_up=self._rank_deltas(deltas, "ban_rate_delta", rising=True, limit=limit),
            ban_rate_down=self._rank_deltas(deltas, "ban_rate_delta", rising=False, limit=limit),
            source=source,
            source_timestamps=timestamps,
            source_timestamp=self._latest_timestamp(timestamps),
            fetched_at=fetched_at,
            stale=stale,
        )

    async def get_meta_insights(
        self,
        insight_type: str,
        *,
        season: str | None = None,
        previous_season: str | None = None,
        rank: str = "all",
        limit: int = 5,
        minimum_matches: int = 100,
    ) -> HeroMetaInsights:
        """Build transparent black-horse, cold-strong, or hot-low-WR boards."""

        aliases = {
            "black_horse": "black_horse",
            "版本黑马": "black_horse",
            "cold_strong": "cold_strong",
            "冷门强者": "cold_strong",
            "hot_trap": "hot_trap",
            "热门陷阱": "hot_trap",
            "热门低胜率": "hot_trap",
        }
        key = aliases.get(str(insight_type).strip().lower(), str(insight_type).strip())
        if key not in {"black_horse", "cold_strong", "hot_trap"}:
            raise MetaQueryError(f"未知历史洞察类型：{insight_type}")
        try:
            rank_key = normalize_rank(rank)
            limit = max(0, int(limit))
        except (TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc
        minimum_matches = self._positive_matches(minimum_matches)
        current_name = season or self.default_historical_seasons(1)[0]
        self.season_code(current_name)
        if key == "black_horse":
            previous_name = previous_season or self.previous_season(current_name)
            previous_code = self.season_code(previous_name)
            current_code = self.season_code(current_name)
            if int(previous_code) >= int(current_code):
                raise MetaQueryError("版本黑马请按旧赛季到新赛季指定，且两个赛季必须不同")
            payloads = await self._load_historical_payloads((previous_code, current_code))
        else:
            previous_name = None
            payloads = await self._load_historical_payloads((current_name,))
        current_payload = payloads[-1]
        current_results = self._results_by_hero(current_payload, rank_key)
        previous_results = (
            self._results_by_hero(payloads[0], rank_key) if key == "black_horse" else {}
        )
        eligible_results = {
            hero_id: result
            for hero_id, result in current_results.items()
            if result.matches >= minimum_matches
        }
        win_median = median(result.win_rate for result in eligible_results.values()) if eligible_results else 0.0
        pick_median = median(result.pick_rate for result in eligible_results.values()) if eligible_results else 0.0
        ban_applies = key == "cold_strong" and rank_key not in {"1", "2"}
        if ban_applies and eligible_results and any(
            result.ban_rate is None for result in eligible_results.values()
        ):
            raise MetaQueryError("当前段位 Ban 数据不足，无法执行完整冷门强者判定")
        ban_median = (
            median(result.ban_rate for result in eligible_results.values() if result.ban_rate is not None)
            if ban_applies
            else None
        )
        items: list[HeroMetaInsight] = []
        for hero_id, result in eligible_results.items():
            previous = previous_results.get(hero_id)
            win_delta = self._delta(result.win_rate, previous.win_rate if previous else None)
            pick_delta = self._delta(result.pick_rate, previous.pick_rate if previous else None)
            ban_delta = self._delta(result.ban_rate, previous.ban_rate if previous else None)
            if key == "black_horse":
                if previous is None or win_delta is None or result.win_rate < win_median or win_delta < 2.0:
                    continue
            elif key == "cold_strong":
                if result.win_rate < win_median or result.pick_rate >= pick_median:
                    continue
                if ban_applies and (ban_median is None or result.ban_rate >= ban_median):
                    continue
            elif result.win_rate >= win_median or result.pick_rate < pick_median:
                continue
            items.append(
                HeroMetaInsight(
                    result=result,
                    previous=previous,
                    win_rate_delta=win_delta,
                    pick_rate_delta=pick_delta,
                    ban_rate_delta=ban_delta,
                )
            )
        if key == "black_horse":
            items.sort(key=lambda item: (item.win_rate_delta or float("-inf"), item.result.win_rate), reverse=True)
            rule = (
                f"当前胜率不低于环境中位数，较上一赛季提升至少 2.0pp，"
                f"且当前样本场次 ≥ {minimum_matches}"
            )
        elif key == "cold_strong":
            items.sort(
                key=lambda item: (
                    item.result.win_rate,
                    -item.result.pick_rate,
                    -(item.result.ban_rate or 0.0),
                ),
                reverse=True,
            )
            ban_rule = "、Ban率低于环境中位数" if ban_applies else "；青铜/白银不纳入 Ban率判断"
            rule = (
                f"胜率不低于环境中位数、选取率低于环境中位数{ban_rule}，"
                f"且样本场次 ≥ {minimum_matches}"
            )
        else:
            items.sort(key=lambda item: (item.result.pick_rate, -item.result.win_rate), reverse=True)
            rule = f"选取率不低于环境中位数、胜率低于环境中位数，且样本场次 ≥ {minimum_matches}"
        source, timestamps, fetched_at, stale = self._history_context(payloads)
        current_identity = season_identity_from_rivalsmeta_code(current_payload.season)
        previous_identity = (
            season_identity_from_rivalsmeta_code(payloads[0].season) if key == "black_horse" else None
        )
        return HeroMetaInsights(
            insight_type=key,
            season_code=str(current_payload.season),
            season_label=current_identity.label,
            previous_season_code=str(payloads[0].season) if key == "black_horse" else None,
            previous_season_label=previous_identity.label if previous_identity else None,
            rank_key=rank_key,
            rank_label=get_rank_label(rank_key),
            rule=rule,
            items=items[:limit],
            source=source,
            source_timestamps=timestamps,
            source_timestamp=self._latest_timestamp(timestamps),
            fetched_at=fetched_at,
            stale=stale,
        )

    async def get_rank_monsters(
        self,
        *,
        season: str | None = None,
        limit: int | None = None,
        minimum_matches: int = 100,
        minimum_win_rate_delta: float = 2.0,
    ) -> RankMonsterBoard:
        """Filter rank-specialists by segment without turning them into a leaderboard."""

        try:
            limit = None if limit is None else max(0, int(limit))
        except (TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc
        minimum_matches = self._positive_matches(minimum_matches)
        try:
            minimum_win_rate_delta = float(minimum_win_rate_delta)
        except (TypeError, ValueError) as exc:
            raise MetaQueryError("分段胜率差阈值必须是数字") from exc
        if minimum_win_rate_delta < 0:
            raise MetaQueryError("分段胜率差阈值不能小于 0")
        payloads = await self._load_historical_payloads((season or self.default_historical_seasons(1)[0],))
        payload = payloads[0]
        all_results = self._results_by_hero(payload, "all", sort_by="win_rate")
        segments: list[RankSegment] = []
        for rank_code in rank_codes("all"):
            ranked = self._results_by_hero(payload, rank_code, sort_by="win_rate")
            candidates: list[RankMonster] = []
            for result in ranked.values():
                overall = all_results.get(result.hero_id)
                if overall is None or result.matches < minimum_matches:
                    continue
                delta = result.win_rate - overall.win_rate
                if delta < minimum_win_rate_delta:
                    continue
                candidates.append(
                    RankMonster(
                        rank_code=rank_code,
                        rank_label=get_rank_label(rank_code),
                        result=result,
                        win_rate_delta=delta,
                    )
                )
            candidates.sort(
                key=lambda item: (
                    item.win_rate_delta if item.win_rate_delta is not None else float("-inf"),
                    item.result.win_rate,
                    item.result.matches,
                ),
                reverse=True,
            )
            if limit is not None:
                candidates = candidates[:limit]
            segments.append(
                RankSegment(
                    rank_code=rank_code,
                    rank_label=get_rank_label(rank_code),
                    items=candidates,
                )
            )
        source, timestamps, fetched_at, stale = self._history_context(payloads)
        identity = season_identity_from_rivalsmeta_code(payload.season)
        return RankMonsterBoard(
            season_code=str(payload.season),
            season_label=identity.label,
            rule=(
                f"按游戏段位顺序列出所有满足条件的英雄：该段位样本场次 ≥ {minimum_matches}，"
                f"且该段位胜率比英雄自身全段位胜率高至少 {minimum_win_rate_delta:.1f}pp；"
                "不进行跨段位排名"
            ),
            segments=segments,
            source=source,
            source_timestamps=timestamps,
            source_timestamp=self._latest_timestamp(timestamps),
            fetched_at=fetched_at,
            stale=stale,
        )

    async def get_single_hero_meta_board(
        self,
        hero_name: str,
        *,
        season: str | None = None,
        rank: str = "all",
    ) -> HeroMetaBoard:
        try:
            hero_id = get_hero_id(hero_name)
        except (TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc
        board = await self.get_hero_meta_board(
            season=season,
            rank=rank,
            sort_by="matches",
            limit=None,
        )
        matches = [item for item in board.heroes if item.hero_id == hero_id]
        if not matches:
            raise MetaQueryError(f"没有找到英雄“{hero_name}”的环境数据")
        board.heroes = matches
        return board

    def _board(
        self,
        payload: RawHeroMetaPayload,
        rank_key: str,
        sort_by: str,
        results: list[HeroMetaResult],
        *,
        role_filter: str | None = None,
        range_start: int | None = None,
        range_end: int | None = None,
        total_count: int | None = None,
        group_by_role: bool = False,
        role_boards: list[HeroMetaRoleBoard] | None = None,
    ) -> HeroMetaBoard:
        source_timestamp = _as_datetime(payload.source_timestamp)
        fetched_at = payload.fetched_at or datetime.now(timezone.utc)
        return HeroMetaBoard(
            season_code=str(payload.season),
            season_label=season_identity_from_rivalsmeta_code(payload.season).label,
            rank_key=rank_key,
            rank_label=get_rank_label(rank_key),
            sort_by=sort_by,
            heroes=results,
            source=payload.source,
            source_timestamp=source_timestamp,
            fetched_at=fetched_at,
            stale=payload.stale,
            role_filter=role_filter,
            range_start=range_start,
            range_end=range_end,
            total_count=len(results) if total_count is None else total_count,
            group_by_role=group_by_role,
            role_boards=role_boards or [],
        )

    def _from_cache_record(self, record: CacheRecord) -> RawHeroMetaPayload:
        try:
            payload = self.source.parse_payload(record.payload)
        except (AttributeError, TypeError, ValueError) as exc:
            raise MetaDataSourceError("Meta 缓存数据格式无效") from exc
        if record.season.isdigit() and payload.season != int(record.season):
            raise MetaDataSourceError("Meta 缓存赛季与缓存键不一致")
        payload.source = record.source
        if record.source_timestamp is not None:
            payload.source_timestamp = record.source_timestamp
        payload.fetched_at = record.fetched_at
        payload.stale = record.stale
        return payload

    @staticmethod
    def _raw_payload(payload: RawHeroMetaPayload) -> dict[str, Any]:
        if isinstance(payload.raw, dict) and payload.raw:
            return payload.raw
        if not is_dataclass(payload):
            raise MetaDataSourceError("Meta 数据无法写入缓存")
        result: dict[str, Any] = {}
        for item in fields(payload):
            if item.name in {"fetched_at", "stale", "source"}:
                continue
            value = getattr(payload, item.name)
            result[item.name] = value
        return result


__all__ = ["MetaService"]
