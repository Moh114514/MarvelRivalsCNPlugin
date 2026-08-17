"""Application service for global hero Meta data."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from typing import Any

from ..datasource.base import DataSourceError
from ..reference.heroes import get_hero_id
from ..reference.ranks import get_rank_label, normalize_rank
from ..reference.seasons import (
    get_season_identity,
    season_identity_from_rivalsmeta_code,
)
from .cache import CacheRecord, MetaDiskCache
from .calculator import _sort_key, calculate_hero_results
from .errors import MetaCacheError, MetaDataSourceError, MetaQueryError
from .models import HeroMetaBoard, HeroMetaOverview, HeroMetaResult, RawHeroMetaPayload


logger = logging.getLogger(__name__)


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
            payload = await self.source.get_hero_stats(season_code)
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

    async def get_hero_meta_board(
        self,
        *,
        season: str | None = None,
        rank: str = "all",
        sort_by: str = "win_rate",
        limit: int | None = 20,
    ) -> HeroMetaBoard:
        try:
            rank_key = normalize_rank(rank)
            sort_key = _sort_key(sort_by)
            self.season_code(season)
        except (TypeError, ValueError) as exc:
            raise MetaQueryError(str(exc)) from exc
        payload = await self.get_raw_hero_meta(season)
        results = calculate_hero_results(
            payload.heroes,
            payload.bans,
            rank=rank_key,
            sort_by=sort_key,
        )
        if limit is not None:
            results = results[: max(0, int(limit))]
        return self._board(payload, rank_key, sort_key, results)

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
