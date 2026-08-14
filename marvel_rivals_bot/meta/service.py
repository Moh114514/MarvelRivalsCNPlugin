"""Application service for global hero Meta data."""

from __future__ import annotations

import time
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from typing import Any

from ..hero_names import get_hero_id
from ..services.rivals import format_season_name, parse_season_name
from .cache import CacheRecord, MetaDiskCache
from .calculator import calculate_hero_results
from .errors import MetaCacheError, MetaDataSourceError
from .models import HeroMetaBoard, HeroMetaResult, RawHeroMetaPayload
from .ranks import get_rank_label, normalize_rank


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
        if not value:
            return self.default_season
        if value.isdigit():
            # Raw numeric codes are useful for internal/debug calls, while
            # command handlers pass user-facing names through this boundary.
            return str(int(value))
        return parse_season_name(value)

    async def get_raw_hero_meta(self, season: str | None = None) -> RawHeroMetaPayload:
        season_code = self.season_code(season)
        memory = self._memory.get(season_code)
        if memory and self.fresh_seconds > 0 and time.monotonic() - memory.loaded_at < self.fresh_seconds:
            return memory.payload
        if memory and self.fresh_seconds <= 0:
            self._memory.pop(season_code, None)

        stale_record = self.cache.load(season_code)
        if stale_record is not None and not stale_record.stale:
            try:
                payload = self._from_cache_record(stale_record)
            except MetaDataSourceError:
                stale_record = None
            else:
                self._memory[season_code] = _MemoryRecord(time.monotonic(), payload)
                return payload

        try:
            payload = await self.source.get_hero_stats(season_code)
        except MetaDataSourceError as remote_error:
            if stale_record is not None:
                try:
                    return self._from_cache_record(stale_record)
                except MetaDataSourceError:
                    pass
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
            pass
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
        payload = await self.get_raw_hero_meta(season)
        rank_key = normalize_rank(rank)
        results = calculate_hero_results(
            payload.heroes,
            payload.bans or [],
            rank=rank_key,
            sort_by=sort_by,
        )
        if limit is not None:
            results = results[: max(0, int(limit))]
        return self._board(payload, rank_key, sort_by, results)

    async def get_single_hero_meta(
        self,
        hero_name: str,
        *,
        season: str | None = None,
        rank: str = "all",
    ) -> HeroMetaResult:
        board = await self.get_single_hero_meta_board(hero_name, season=season, rank=rank)
        return board.heroes[0]

    async def get_single_hero_meta_board(
        self,
        hero_name: str,
        *,
        season: str | None = None,
        rank: str = "all",
    ) -> HeroMetaBoard:
        try:
            hero_id = get_hero_id(hero_name)
        except ValueError as exc:
            raise MetaDataSourceError(str(exc)) from exc
        board = await self.get_hero_meta_board(
            season=season,
            rank=rank,
            sort_by="matches",
            limit=None,
        )
        matches = [item for item in board.heroes if item.hero_id == hero_id]
        if not matches:
            raise MetaDataSourceError(f"没有找到英雄“{hero_name}”的环境数据")
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
            season_label=format_season_name(payload.season),
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
