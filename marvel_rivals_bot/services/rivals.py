from __future__ import annotations

import asyncio
import time
import re
from datetime import date, datetime
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar

from ..datasource.base import DataSourceError, GameMode, RivalsDataSource
from ..game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
from ..reference.dates import GAME_TZ, game_date_window
from ..reference.time_ranges import MAX_WINDOW_SECONDS, parse_match_time_window
from ..reference.heroes import HERO_ROLE_LABELS, format_hero_name, get_hero_id, get_hero_identity, get_hero_name
from ..models import (
    HeroQueryResult,
    MatchPlayer,
    MatchRecord,
    MatchSummaryPage,
    MatchTimeWindow,
    MatchWindowReport,
    ModeStats,
    PlayerHeroStats,
    PlayerProfile,
    PlayerStats,
    ROLE_ORDER,
    WindowHeroStats,
    WindowStats,
    RoleWindowStats,
)
from ..reference.seasons import format_season_name as _format_season_name
from ..reference.seasons import parse_season_name as _parse_season_name
from ..reference.seasons import season_identity_from_cn_code, season_identity_from_name


CacheValue = TypeVar("CacheValue")
_MATCH_UID_PREFIX_RE = re.compile(r"^matchuid\s*[:=：]\s*(.+)$", re.IGNORECASE)


def normalize_match_uid(value: str) -> str:
    candidate = str(value).strip()
    match = _MATCH_UID_PREFIX_RE.match(candidate)
    return match.group(1).strip() if match else candidate


def format_season_name(code: str | int) -> str:
    return _format_season_name(code)


def parse_season_name(value: str) -> str:
    try:
        return _parse_season_name(value)
    except ValueError as exc:
        # Keep the legacy façade's DataSourceError contract while the
        # canonical reference module stays independent of data sources.
        raise DataSourceError(str(exc)) from exc


class RivalsService:
    MATCH_PAGE_SIZE = 100
    MAX_MATCH_PAGES = 20
    MATCH_DETAIL_BATCH_SIZE = 10
    DETAIL_MAX_CONCURRENCY = 2

    def __init__(
        self,
        source: RivalsDataSource,
        cache_seconds: float = 60,
        *,
        hero_batch_size: int = 32,
        hero_max_concurrency: int = 4,
        max_inflight_requests: int = 8,
        daily_cache_seconds: float = 86400,
        daily_current_cache_seconds: float = 60,
        match_page_size: int = MATCH_PAGE_SIZE,
        max_match_pages: int = MAX_MATCH_PAGES,
        match_detail_batch_size: int = MATCH_DETAIL_BATCH_SIZE,
        detail_max_concurrency: int = DETAIL_MAX_CONCURRENCY,
    ):
        self.source = source
        self.cache_seconds = max(0, cache_seconds)
        self.hero_batch_size = max(1, int(hero_batch_size))
        self.hero_max_concurrency = max(1, int(hero_max_concurrency))
        self.max_inflight_requests = max(1, int(max_inflight_requests))
        self.daily_cache_seconds = max(0, float(daily_cache_seconds))
        self.daily_current_cache_seconds = max(0, float(daily_current_cache_seconds))
        self.match_page_size = max(1, int(match_page_size))
        self.max_match_pages = max(1, int(max_match_pages))
        self.match_detail_batch_size = max(1, int(match_detail_batch_size))
        self.detail_max_concurrency = max(1, int(detail_max_concurrency))
        self._request_semaphore = asyncio.Semaphore(self.max_inflight_requests)
        self._hero_request_semaphore: asyncio.Semaphore | None = None
        self._inflight: dict[str, asyncio.Task[Any]] = {}
        self._player_cache: dict[str, tuple[float, PlayerStats]] = {}
        self._profile_cache: dict[str, tuple[float, PlayerProfile]] = {}
        self._matches_cache: dict[str, tuple[float, list[MatchRecord]]] = {}
        self._hero_cache: dict[str, tuple[float, HeroQueryResult]] = {}
        self._match_detail_cache: dict[str, tuple[float, dict]] = {}
        self._window_cache: dict[str, tuple[float, MatchWindowReport]] = {}
        # Keep the old attribute as a compatibility view for integrations
        # that inspected it during the daily-only release.
        self._daily_cache = self._window_cache

    @property
    def request_semaphore(self) -> asyncio.Semaphore:
        """Shared external-request limiter for sibling services."""

        return self._request_semaphore

    async def get_player_stats(self, uid: str, season: str | None = None) -> PlayerStats:
        season_code = self._season_code(season)
        cache_key = f"{uid}:{season_code}"
        cached = self._cached(self._player_cache, cache_key)
        if cached is not None:
            return cached

        async def load() -> PlayerStats:
            stats = await self._request(lambda: self.source.get_player(uid, season_code))
            self._player_cache[cache_key] = (time.monotonic(), stats)
            return stats

        return await self._singleflight(f"player:{uid}:{season_code}", load)

    async def player_text(self, uid: str, season: str | None = None) -> str:
        return format_player(await self.get_player_stats(uid, season))

    async def get_player_profile(self, uid: str, season: str | None = None) -> PlayerProfile:
        """Load only identity and current rank context for Meta commands."""

        season_code = self._season_code(season)
        cache_key = f"{uid}:{season_code}:profile"
        cached = self._cached(self._profile_cache, cache_key)
        if cached is not None:
            return cached
        loader = getattr(self.source, "get_player_profile", None)
        if callable(loader):
            profile = await self._request(lambda: loader(uid, season_code))
        else:
            stats = await self._request(lambda: self.source.get_player(uid, season_code))
            profile = stats.profile
        self._profile_cache[cache_key] = (time.monotonic(), profile)
        return profile

    async def get_player_profile_history(self, uid: str) -> PlayerProfile:
        """Load the light profile history, with a legacy-source fallback."""

        loader = getattr(self.source, "get_player_profile_history", None)
        if callable(loader):
            try:
                return await self._request(lambda: loader(uid))
            except NotImplementedError:
                pass
        profile_loader = getattr(self.source, "get_player_profile", None)
        if callable(profile_loader):
            return await self._request(lambda: profile_loader(uid))
        stats = await self._request(lambda: self.source.get_player(uid))
        return stats.profile

    async def get_hero_profiles_batch(
        self,
        uid: str,
        hero_ids: list[int | str],
        season: str | None,
        game_mode: GameMode | int,
        batch_size: int | None = None,
    ) -> list[PlayerHeroStats]:
        """Load returned HeroCareer rows in bounded batches.

        Missing rows are omitted rather than represented by fabricated stats.
        Sources without the batched loader retain a one-hero compatibility
        fallback for existing fake and legacy adapters.
        """

        batch_size = self.hero_batch_size if batch_size is None else int(batch_size)
        if batch_size <= 0:
            raise DataSourceError("batch_size 必须是正整数")
        season_text = str(season).strip() if season is not None else ""
        season_code = str(int(season_text)) if season_text.isdigit() else self._season_code(season)
        normalized_ids: list[int | str] = []
        seen: set[str] = set()
        for hero_id in hero_ids:
            value = str(hero_id).strip()
            if value and value not in seen:
                normalized_ids.append(int(value) if value.isdigit() else value)
                seen.add(value)
        if not normalized_ids:
            return []

        chunks = [normalized_ids[index:index + batch_size] for index in range(0, len(normalized_ids), batch_size)]
        if self._hero_request_semaphore is None:
            self._hero_request_semaphore = asyncio.Semaphore(self.hero_max_concurrency)
        loader = getattr(self.source, "load_hero_career", None)
        inherited_loader = (
            isinstance(self.source, RivalsDataSource)
            and getattr(type(self.source), "load_hero_career", None)
            is RivalsDataSource.load_hero_career
        )
        if callable(loader) and not inherited_loader:
            try:
                return await self._load_hero_batches(
                    loader, uid, chunks, season_code, game_mode, self._hero_request_semaphore
                )
            except NotImplementedError:
                pass
        return await self._load_hero_legacy_fallback(uid, normalized_ids, season_code, game_mode)

    async def _load_hero_batches(
        self,
        loader: Any,
        uid: str,
        chunks: list[list[int | str]],
        season: str,
        game_mode: GameMode | int,
        semaphore: asyncio.Semaphore,
    ) -> list[PlayerHeroStats]:
        async def load_chunk(chunk: list[str]) -> list[PlayerHeroStats]:
            async with semaphore:
                payload = await self._request(lambda: loader(uid, chunk, season, game_mode))
            parser = getattr(self.source, "parse_hero_career", None)
            if callable(parser):
                try:
                    parsed = parser(payload, chunk, game_mode)
                    if parsed is not None:
                        return list(parsed)
                except NotImplementedError:
                    pass
            return _parse_generic_hero_career(payload, chunk, game_mode)

        groups = await asyncio.gather(*(load_chunk(chunk) for chunk in chunks))
        result: list[PlayerHeroStats] = []
        returned: set[str] = set()
        for group in groups:
            for hero in group:
                if hero.hero_id not in returned:
                    result.append(hero)
                    returned.add(hero.hero_id)
        return result

    async def _load_hero_legacy_fallback(
        self,
        uid: str,
        hero_ids: list[int | str],
        season: str,
        game_mode: GameMode | int,
    ) -> list[PlayerHeroStats]:
        async def load_one(hero_id: int | str) -> PlayerHeroStats | None:
            if self._hero_request_semaphore is None:
                self._hero_request_semaphore = asyncio.Semaphore(self.hero_max_concurrency)
            async with self._hero_request_semaphore:
                try:
                    profile_loader = getattr(self.source, "get_hero_profile", None)
                    if callable(profile_loader):
                        profile = await self._request(
                            lambda: profile_loader(uid, str(hero_id), season)
                        )
                        return profile if isinstance(profile, PlayerHeroStats) else None
                    payload = await self._request(
                        lambda: self.source.get_hero(uid, str(hero_id), season)
                    )
                except (DataSourceError, NotImplementedError):
                    return None
            parsed = _parse_generic_hero_career(payload, [hero_id], game_mode)
            return parsed[0] if parsed else None

        values = await asyncio.gather(*(load_one(hero_id) for hero_id in hero_ids))
        return [value for value in values if value is not None]

    async def get_recent_matches(self, uid: str, season: str | None = None) -> list[MatchRecord]:
        season_code = self._season_code(season)
        cache_key = f"{uid}:{season_code}"
        cached = self._cached(self._matches_cache, cache_key)
        if cached is not None:
            return cached

        async def load() -> list[MatchRecord]:
            summary_loader = getattr(self.source, "get_match_summary_page", None)
            inherited_loader = (
                isinstance(self.source, RivalsDataSource)
                and getattr(type(self.source), "get_match_summary_page", None)
                is RivalsDataSource.get_match_summary_page
            )
            if callable(summary_loader) and not inherited_loader:
                try:
                    page = await self._request(
                        lambda: summary_loader(uid, season=season_code, page=0, page_size=10)
                    )
                    matches = _summary_page_items(page)
                    matches = await self._enrich_match_summaries(uid, matches)
                except NotImplementedError:
                    matches = await self._request(lambda: self.source.get_recent_matches(uid, season_code))
            else:
                matches = await self._request(lambda: self.source.get_recent_matches(uid, season_code))
            records = _coerce_match_records(matches, uid)
            self._matches_cache[cache_key] = (time.monotonic(), records)
            return records

        return await self._singleflight(f"recent:{uid}:{season_code}", load)

    async def matches_text(self, uid: str, season: str | None = None) -> str:
        season_code = self._season_code(season)
        return format_matches(await self.get_recent_matches(uid, season), season_code)

    async def get_hero_stats(self, uid: str, hero_name: str, season: str | None = None) -> HeroQueryResult:
        season_code = self._season_code(season)
        try:
            hero_id = str(get_hero_id(hero_name))
        except ValueError as exc:
            raise DataSourceError(str(exc)) from exc
        cache_key = f"{uid}:{hero_id}:{season_code}"
        cached = self._cached(self._hero_cache, cache_key)
        if cached is not None:
            return cached

        async def load() -> HeroQueryResult:
            identity = get_hero_identity(hero_id)
            profile_loader = getattr(self.source, "get_hero_profile", None)
            if callable(profile_loader):
                profile = await self._request(
                    lambda: profile_loader(uid, hero_id, season_code)
                )
                result = HeroQueryResult(
                    uid=uid,
                    hero_id=hero_id,
                    hero_name=profile.hero_name or hero_name,
                    season=season_code,
                    payload={"data": {"careers": [profile.raw]}},
                    stats=profile,
                    role=identity.role,
                    role_label=HERO_ROLE_LABELS.get(identity.role, "未知职责"),
                )
            else:
                result = HeroQueryResult(
                    uid=uid,
                    hero_id=hero_id,
                    hero_name=hero_name,
                    season=season_code,
                    payload=await self._request(
                        lambda: self.source.get_hero(uid, hero_id, season_code)
                    ),
                    role=identity.role,
                    role_label=HERO_ROLE_LABELS.get(identity.role, "未知职责"),
                )
            self._hero_cache[cache_key] = (time.monotonic(), result)
            return result

        return await self._singleflight(f"hero:{uid}:{hero_id}:{season_code}", load)

    async def hero_text(self, uid: str, hero_name: str, season: str | None = None) -> str:
        result = await self.get_hero_stats(uid, hero_name, season)
        return format_hero_result(result)

    async def get_match_detail(self, match_uid: str) -> dict:
        normalized_uid = normalize_match_uid(match_uid)
        cache_key = normalized_uid
        cached = self._cached(self._match_detail_cache, cache_key)
        if cached is not None:
            return cached

        async def load() -> dict:
            payload = await self._request(lambda: self.source.get_summary_detail(normalized_uid))
            self._cache_detail_payload(payload)
            if self.cache_seconds > 0:
                self._match_detail_cache[cache_key] = (time.monotonic(), payload)
            return payload

        return await self._singleflight(f"match:{cache_key}", load)

    async def match_detail_text(self, match_uid: str) -> str:
        return format_match_detail(await self.get_match_detail(match_uid))

    async def get_matches_by_time_range(
        self,
        uid: str,
        season: str | None = None,
        *,
        start_timestamp: int,
        end_timestamp: int,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all Summary rows in a server-filtered half-open time range."""

        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        if int(end_timestamp) <= int(start_timestamp):
            raise DataSourceError("时间范围结束时间必须晚于开始时间")
        if int(end_timestamp) - int(start_timestamp) > MAX_WINDOW_SECONDS:
            raise DataSourceError("单次战绩回顾最多查询 7 天")
        season_text = str(season or "").strip()
        season_code = season_text if season_text.isdigit() else self._season_code(season) if season_text else None
        loader = getattr(self.source, "get_match_summary_page", None)
        inherited_loader = (
            isinstance(self.source, RivalsDataSource)
            and getattr(type(self.source), "get_match_summary_page", None)
            is RivalsDataSource.get_match_summary_page
        )
        if not callable(loader) or inherited_loader:
            raise DataSourceError("当前数据源不支持按时间范围查询对局")
        page_size = self.match_page_size if page_size is None else max(1, int(page_size))
        max_pages = self.max_match_pages if max_pages is None else max(1, int(max_pages))
        matches: list[dict] = []
        for page_number in range(max_pages):
            result = await self._request(
                lambda page_number=page_number: loader(
                    uid,
                    season=season_code,
                    page=page_number,
                    page_size=page_size,
                    start_timestamp=int(start_timestamp),
                    end_timestamp=int(end_timestamp),
                )
            )
            rows = _summary_page_items(result)
            matches.extend(rows)
            if len(rows) < page_size:
                break
        return matches

    async def get_match_window_report(
        self,
        uid: str,
        window: MatchTimeWindow,
        *,
        season: str | None = None,
    ) -> MatchWindowReport:
        """Fetch, normalize and aggregate every match in ``window``."""

        if not isinstance(window, MatchTimeWindow):
            raise DataSourceError("时间范围无效")
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        now = datetime.now(GAME_TZ)
        cache_key = f"match-window:{uid}:{window.start_timestamp}:{window.end_timestamp}"
        contains_now = window.end_timestamp >= int(now.timestamp()) - 2
        cache_ttl = self.daily_current_cache_seconds if contains_now else self.daily_cache_seconds
        cached = self._window_cache.get(cache_key)
        if cached is not None and cache_ttl > 0 and time.monotonic() - cached[0] < cache_ttl:
            return cached[1]

        async def load() -> MatchWindowReport:
            summaries = await self.get_matches_by_time_range(
                uid,
                season,
                start_timestamp=window.start_timestamp,
                end_timestamp=window.end_timestamp,
            )
            details = await self.get_summary_details([_match_uid(item) for item in summaries])
            records: list[MatchRecord] = []
            player_name = ""
            for summary in summaries:
                match_uid = _match_uid(summary)
                detail = details.get(match_uid)
                target = _target_player(detail, uid)
                if target is None:
                    target = _target_player(summary.get("matchPlayer"), uid)
                if target is None and isinstance(summary.get("matchPlayer"), Mapping):
                    target = dict(summary["matchPlayer"])
                target = target or {"playerUid": uid}
                player_name = player_name or _text_value(target, "nickName", "playerName", "name")
                records.append(_match_record(summary, detail, target, match_uid, uid))
            if not player_name:
                player_name = await self._fallback_player_name(uid, self._season_code(season))
            report = _build_match_window_report(
                uid=uid,
                player_name=player_name or uid,
                window=window,
                season=self._season_code(season) if season else "",
                matches=records,
            )
            if cache_ttl > 0:
                self._window_cache[cache_key] = (time.monotonic(), report)
            return report

        return await self._singleflight(cache_key, load)

    async def get_window_report(
        self,
        uid: str,
        window: MatchTimeWindow,
        *,
        season: str | None = None,
    ) -> MatchWindowReport:
        return await self.get_match_window_report(uid, window, season=season)

    async def get_daily_report(
        self,
        uid: str,
        target_date: date,
        season: str | None = None,
    ) -> MatchWindowReport:
        """Compatibility shortcut: build a full Beijing calendar-day window."""

        if not isinstance(target_date, date):
            raise DataSourceError("每日战绩日期无效")
        window = parse_match_time_window([target_date.isoformat()])
        return await self.get_match_window_report(uid, window, season=season)

    async def get_summary_details(self, match_uids: list[str]) -> dict[str, dict[str, Any]]:
        """Load details in batches, reusing the per-match cache."""

        normalized: list[str] = []
        seen: set[str] = set()
        for value in match_uids:
            uid = normalize_match_uid(str(value))
            if uid and uid not in seen:
                normalized.append(uid)
                seen.add(uid)
        if not normalized:
            return {}

        details: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        for match_uid in normalized:
            cached = self._cached(self._match_detail_cache, match_uid)
            if cached is None:
                missing.append(match_uid)
                continue
            rows = _detail_rows(cached)
            row = _detail_by_uid(rows).get(match_uid)
            if row is not None:
                details[match_uid] = row

        if not missing:
            return details

        batch_loader = getattr(self.source, "get_summary_details", None)
        inherited_batch_loader = (
            isinstance(self.source, RivalsDataSource)
            and getattr(type(self.source), "get_summary_details", None)
            is RivalsDataSource.get_summary_details
        )
        semaphore = asyncio.Semaphore(self.detail_max_concurrency)
        batches = [
            missing[index:index + self.match_detail_batch_size]
            for index in range(0, len(missing), self.match_detail_batch_size)
        ]

        async def load_batch(batch: list[str]) -> list[dict[str, Any]]:
            async with semaphore:
                if callable(batch_loader) and not inherited_batch_loader:
                    payload = await self._request(lambda: batch_loader(batch))
                    rows = _detail_rows(payload)
                else:
                    payloads = await asyncio.gather(*(self.get_match_detail(item) for item in batch))
                    rows = [row for payload in payloads for row in _detail_rows(payload)]
                for row in rows:
                    match_uid = _match_uid(row)
                    if match_uid:
                        self._cache_detail_row(match_uid, row)
                return rows

        for rows in await asyncio.gather(*(load_batch(batch) for batch in batches)):
            for row in rows:
                match_uid = _match_uid(row)
                if match_uid in seen:
                    details[match_uid] = row
        return details

    async def _fallback_player_name(self, uid: str, season_code: str) -> str:
        loader = getattr(self.source, "get_player_profile", None)
        if not callable(loader):
            return uid
        try:
            profile = await self._request(lambda: loader(uid, season_code))
        except Exception:
            return uid
        return str(getattr(profile, "name", "") or uid)

    async def _enrich_match_summaries(self, uid: str, matches: list[dict]) -> list[dict]:
        details = await self.get_summary_details([_match_uid(item) for item in matches])
        for match in matches:
            detail = details.get(_match_uid(match))
            if detail is not None:
                match["_matchDetail"] = dict(detail)
            target = _target_player(detail, uid)
            if target is None and isinstance(match.get("matchPlayer"), Mapping):
                target = dict(match["matchPlayer"])
            if target is not None:
                match["matchPlayer"] = dict(target)
        return matches

    def _cache_detail_payload(self, payload: dict[str, Any]) -> None:
        for row in _detail_rows(payload):
            match_uid = _match_uid(row)
            if match_uid:
                self._cache_detail_row(match_uid, row)

    def _cache_detail_row(self, match_uid: str, row: dict[str, Any]) -> None:
        if self.cache_seconds <= 0:
            return
        self._match_detail_cache[match_uid] = (
            time.monotonic(),
            {"data": {"matches": [dict(row)]}},
        )

    def _season_code(self, season: str | None) -> str:
        if season is None or not str(season).strip():
            default_season = getattr(self.source, "default_season", "19")
            try:
                return season_identity_from_cn_code(default_season).for_provider("cn")
            except ValueError as exc:
                raise DataSourceError(str(exc)) from exc
        try:
            return season_identity_from_name(season).for_provider("cn")
        except ValueError as exc:
            raise DataSourceError(str(exc)) from exc

    def season_code(self, season: str | None = None) -> str:
        return self._season_code(season)

    async def _request(self, operation: Callable[[], Awaitable[CacheValue]]) -> CacheValue:
        async with self._request_semaphore:
            return await operation()

    async def _singleflight(
        self,
        key: str,
        factory: Callable[[], Awaitable[CacheValue]],
    ) -> CacheValue:
        task = self._inflight.get(key)
        if task is None:
            task_holder: dict[str, asyncio.Task[CacheValue]] = {}

            async def run() -> CacheValue:
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

    def _cached(self, cache: dict[str, tuple[float, CacheValue]], key: str) -> CacheValue | None:
        if self.cache_seconds <= 0:
            return None
        item = cache.get(key)
        if item and time.monotonic() - item[0] < self.cache_seconds:
            return item[1]
        cache.pop(key, None)
        return None


def _summary_page_items(value: MatchSummaryPage | Mapping[str, Any] | Any) -> list[dict[str, Any]]:
    if isinstance(value, MatchSummaryPage):
        return [dict(item) for item in value.match_info if isinstance(item, Mapping)]
    if not isinstance(value, Mapping):
        return []
    data: Any = value.get("data", value)
    if isinstance(data, Mapping):
        data = data.get(
            "matchInfo",
            data.get("matches", data.get("matchList", data.get("records", data.get("list", [])))),
        )
    return [dict(item) for item in data if isinstance(item, Mapping)] if isinstance(data, list) else []


def _detail_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if not isinstance(value, Mapping):
        return []
    data: Any = value.get("data", value)
    if isinstance(data, Mapping):
        matches = data.get("matches")
        if matches is None:
            matches = data.get("matchInfo", data.get("list"))
        if isinstance(matches, list):
            return [dict(item) for item in matches if isinstance(item, Mapping)]
        # A few test and compatibility adapters return a UID -> match map.
        if matches is None and all(isinstance(item, Mapping) for item in data.values()):
            rows = []
            for key, item in data.items():
                row = dict(item)
                if not _match_uid(row):
                    row["matchUid"] = str(key)
                rows.append(row)
            return rows
    return [dict(data)] if isinstance(data, Mapping) and _match_uid(data) else []


def _match_uid(value: Mapping[str, Any] | Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    for key in ("matchUid", "matchUID", "matchUids", "uid", "id"):
        item = value.get(key)
        if item not in (None, ""):
            return normalize_match_uid(str(item))
    return ""


def _detail_by_uid(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        match_uid: row
        for row in rows
        if (match_uid := _match_uid(row))
    }


def _text_value(value: Mapping[str, Any] | Any, *keys: str) -> str:
    if not isinstance(value, Mapping):
        return ""
    for key in keys:
        item = value.get(key)
        if item not in (None, ""):
            return str(item)
    return ""


def _target_player(value: Mapping[str, Any] | Any, uid: str) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    players = value.get("matchPlayers")
    if not isinstance(players, list):
        return value if _same_uid(value.get("playerUid", value.get("uid")), uid) else None
    for player in players:
        if isinstance(player, Mapping) and _same_uid(player.get("playerUid", player.get("uid")), uid):
            return dict(player)
    return None


def _same_uid(value: Any, uid: str) -> bool:
    if value in (None, ""):
        return False
    try:
        return int(value) == int(uid)
    except (TypeError, ValueError):
        return str(value).strip() == str(uid).strip()


def _number_value(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_value(value: Any, default: int = 0) -> int:
    number = _number_value(value)
    return int(round(number)) if number is not None else default


def _bool_result(value: Any) -> bool | None:
    if value in (1, "1", True, "true", "True"):
        return True
    if value in (0, "0", False, "false", "False"):
        return False
    return None


def _first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _coerce_match_records(value: Any, uid: str) -> list[MatchRecord]:
    records: list[MatchRecord] = []
    if not isinstance(value, list):
        return records
    for item in value:
        if isinstance(item, MatchRecord):
            records.append(item)
            continue
        if not isinstance(item, Mapping):
            continue
        summary = dict(item)
        detail = summary.get("_matchDetail") or summary.get("detail")
        if not isinstance(detail, Mapping):
            detail = None
        target = _target_player(detail, uid) or _target_player(summary.get("matchPlayer"), uid)
        if target is None and isinstance(summary.get("matchPlayer"), Mapping):
            target = dict(summary["matchPlayer"])
        records.append(_match_record(summary, detail, target or {"playerUid": uid}, _match_uid(summary), uid))
    return records


def _match_record(
    summary: Mapping[str, Any],
    detail: Mapping[str, Any] | None,
    target: Mapping[str, Any],
    match_uid: str,
    uid: str,
) -> MatchRecord:
    detail = detail or {}
    hero_value = _first_value(target.get("curHeroId"), target.get("heroId"))
    player_uid = _text_value(target, "playerUid", "uid") or str(uid)
    player = MatchPlayer(
        player_uid=player_uid,
        hero_id=str(hero_value) if hero_value not in (None, "") else None,
        is_win=_bool_result(target.get("isWin")),
        kills=_optional_int(target, "k", "kills"),
        deaths=_optional_int(target, "d", "deaths"),
        assists=_optional_int(target, "a", "assists"),
        hero_damage=_optional_int(target, "totalHeroDamage", "heroDamage"),
        healing=_optional_int(target, "totalHeroHeal", "totalHeal", "heroHeal", "heal"),
        damage_taken=_optional_int(target, "totalDamageTaken", "damageTaken"),
        player_name=_text_value(target, "nickName", "playerName", "name"),
        raw=dict(target),
    )
    return MatchRecord(
        match_uid=match_uid,
        timestamp=_optional_int({"value": _first_value(summary.get("matchTimeStamp"), detail.get("matchTimeStamp"))}, "value"),
        game_mode_id=_optional_int({"value": _first_value(summary.get("gameModeId"), detail.get("gameModeId"))}, "value"),
        play_mode_id=_optional_int({"value": _first_value(summary.get("playModeId"), detail.get("playModeId"))}, "value"),
        map_id=_optional_int({"value": _first_value(summary.get("matchMapId"), detail.get("matchMapId"))}, "value"),
        duration_seconds=_number_value(_first_value(summary.get("matchPlayDuration"), detail.get("matchPlayDuration"))),
        player=player,
        raw={**dict(summary), "detail": dict(detail), "matchPlayer": dict(target)},
    )


def _optional_int(value: Mapping[str, Any], *keys: str) -> int | None:
    number = _number_value(_first_value(*(value.get(key) for key in keys)))
    return int(round(number)) if number is not None else None


def _build_match_window_report(
    *,
    uid: str,
    player_name: str,
    window: MatchTimeWindow,
    season: str,
    matches: list[MatchRecord],
) -> MatchWindowReport:
    total = WindowStats()
    quick = WindowStats()
    competitive = WindowStats()
    other = WindowStats()
    roles = {role: RoleWindowStats(role=role) for role in ROLE_ORDER}
    hero_map: dict[str, WindowHeroStats] = {}
    for match in matches:
        bucket = quick if match.game_mode_id == 1 else competitive if match.game_mode_id == 2 else other
        for stats in (total, bucket):
            _accumulate_mode(stats, match)
        role = _match_role(match)
        if role in roles:
            _accumulate_mode(roles[role], match)
        if match.player.hero_id:
            hero = hero_map.setdefault(
                match.player.hero_id,
                WindowHeroStats(
                    hero_id=match.player.hero_id,
                    hero_name=_daily_hero_name(match.player.hero_id),
                    role=role,
                ),
            )
            _accumulate_hero(hero, match)
    heroes = sorted(
        hero_map.values(),
        key=lambda item: (-item.matches, -item.play_time_seconds, item.hero_id),
    )
    for hero in heroes:
        denominator = roles.get(hero.role).matches if hero.role in roles else total.matches
        hero.usage_rate = hero.matches * 100 / denominator if denominator else None
    return MatchWindowReport(
        uid=uid,
        player_name=player_name,
        window=window,
        total=total,
        quick=quick,
        competitive=competitive,
        other=other,
        heroes=heroes,
        matches=matches,
        season=season,
        roles=roles,
    )


def _build_daily_report(
    *,
    uid: str,
    player_name: str,
    target_date: date,
    season: str,
    matches: list[MatchRecord],
) -> MatchWindowReport:
    """Compatibility helper retained for older integrations."""

    start_timestamp, end_timestamp = game_date_window(target_date)
    start = datetime.fromtimestamp(start_timestamp, GAME_TZ)
    end = datetime.fromtimestamp(end_timestamp, GAME_TZ)
    window = MatchTimeWindow(
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        start_at=start,
        end_at=end,
        timezone="Asia/Shanghai",
        label=f"{target_date.year}年{target_date.month}月{target_date.day}日",
    )
    return _build_match_window_report(
        uid=uid, player_name=player_name, window=window, season=season, matches=matches
    )


_daily_match = _match_record


def _match_role(match: MatchRecord) -> str | None:
    if not match.player.hero_id:
        return None
    return get_hero_identity(match.player.hero_id).role


def _accumulate_mode(stats: WindowStats, match: MatchRecord) -> None:
    stats.matches += 1
    if match.player.is_win is True:
        stats.wins += 1
    elif match.player.is_win is False:
        stats.losses += 1
    stats.kills += match.player.kills or 0
    stats.deaths += match.player.deaths or 0
    stats.assists += match.player.assists or 0
    stats.play_time_seconds += match.duration_seconds or 0
    if match.player.hero_damage is not None:
        stats.hero_damage = (stats.hero_damage or 0) + match.player.hero_damage
        stats.damage_samples += 1
    if match.player.healing is not None:
        stats.healing = (stats.healing or 0) + match.player.healing
        stats.healing_samples += 1
    if match.player.damage_taken is not None:
        stats.damage_taken = (stats.damage_taken or 0) + match.player.damage_taken
        stats.damage_taken_samples += 1


def _accumulate_hero(stats: WindowHeroStats, match: MatchRecord) -> None:
    stats.matches += 1
    if match.player.is_win is True:
        stats.wins += 1
    elif match.player.is_win is False:
        stats.losses += 1
    stats.kills += match.player.kills or 0
    stats.deaths += match.player.deaths or 0
    stats.assists += match.player.assists or 0
    stats.play_time_seconds += match.duration_seconds or 0
    if match.player.hero_damage is not None:
        stats.hero_damage = (stats.hero_damage or 0) + match.player.hero_damage
        stats.damage_samples += 1
    if match.player.healing is not None:
        stats.healing = (stats.healing or 0) + match.player.healing
        stats.healing_samples += 1
    if match.player.damage_taken is not None:
        stats.damage_taken = (stats.damage_taken or 0) + match.player.damage_taken
        stats.damage_taken_samples += 1


def _daily_hero_name(hero_id: str) -> str:
    name = get_hero_name(hero_id)
    if name == f"英雄 {hero_id}":
        return f"未知英雄（{hero_id}）"
    return name


def _fmt(value: int | float | None, fallback: str = "-") -> str:
    if value is None:
        return fallback
    return f"{value:.1f}" if isinstance(value, float) and not value.is_integer() else str(int(value))


def _generic_hero_rows(payload: Any) -> list[dict[str, Any]]:
    data = payload.get("data", payload) if isinstance(payload, Mapping) else payload
    if isinstance(data, list):
        rows = data
    elif isinstance(data, Mapping):
        rows = data.get("careers", data.get("heros", data.get("heroes", data.get("heroList", []))))
    else:
        rows = []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _generic_number(row: Mapping[str, Any], *keys: str) -> int | float | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value) if isinstance(value, str) and "." in value else int(value)
        except (TypeError, ValueError):
            continue
    return None


def _parse_generic_hero_career(
    payload: Any,
    hero_ids: list[int | str],
    game_mode: GameMode | int,
) -> list[PlayerHeroStats]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, PlayerHeroStats)]
    requested = {str(item) for item in hero_ids}
    try:
        mode = GameMode(int(game_mode))
    except (TypeError, ValueError):
        mode = GameMode.COMPETITIVE
    result: list[PlayerHeroStats] = []
    for row in _generic_hero_rows(payload):
        hero_id = str(row.get("heroId", row.get("id", "")))
        if not hero_id or hero_id not in requested:
            continue
        matches = _generic_number(
            row, "totalMatchCount", "matchCount", "matches", "totalMatches", "gameCount"
        )
        wins = _generic_number(
            row, "totalMatchWinCount", "totalWinCount", "winCount", "wins"
        )
        win_rate = _generic_number(row, "winRate")
        if win_rate is None and matches and wins is not None:
            win_rate = wins * 100 / matches
        scope = ModeStats(
            matches=round(matches) if matches is not None else None,
            wins=round(wins) if wins is not None else None,
            win_rate=win_rate,
            kills=_generic_number(row, "k", "kills"),
            deaths=_generic_number(row, "d", "deaths"),
            assists=_generic_number(row, "a", "assists"),
            play_time_seconds=_generic_number(row, "totalPlayTime", "playTime"),
        )
        hero = PlayerHeroStats(
            hero_id=hero_id,
            hero_name=format_hero_name(hero_id),
            raw=dict(row),
        )
        if mode is GameMode.QUICK:
            hero.quick = scope
        else:
            hero.competitive = scope
            hero.ranked = hero.competitive
        hero.total = scope
        hero.total_matches = scope.matches
        hero.total_wins = scope.wins
        hero.total_win_rate = scope.win_rate
        hero.total_play_time_seconds = scope.play_time_seconds
        result.append(hero)
    return result


def _duration(seconds: int | float | None) -> str:
    if not isinstance(seconds, (int, float)):
        return "-"
    minutes, remain = divmod(int(seconds), 60)
    return f"{minutes}:{remain:02d}"


def _hours(seconds: int | float | None) -> str:
    if not isinstance(seconds, (int, float)):
        return "-"
    return f"{seconds / 3600:.2f} 小时"


def _count(value: int | float | None, fallback: str = "-") -> str:
    if not isinstance(value, (int, float)):
        return fallback
    return str(round(value))


def _time(timestamp: Any) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "未知时间"


def _mode_matches(mode: ModeStats, fallback: int | float | None = None) -> str:
    value = mode.matches if mode.matches is not None else fallback
    return _count(value)


def _mode_rate(mode: ModeStats, fallback: float | None = None) -> str:
    value = mode.win_rate if mode.win_rate is not None else fallback
    return _fmt(value) + "%" if value is not None else "-"


def _mode_average(total: int | float | None, matches: int | None) -> str:
    if total is None or matches is None or matches <= 0:
        return "-"
    return _fmt(total / matches)


def format_player(stats: PlayerStats) -> str:
    p, s = stats.profile, stats.summary
    lines = [f"漫威争锋国服个人资料（{format_season_name(stats.season)}的数据）", f"玩家：{p.name}", f"UID：{p.uid}"]
    if p.level is not None:
        lines.append(f"等级：{p.level}")
    if p.rank_game_season:
        lines.append(f"段位：{p.rank_game_season}")
    lines += [
        "",
        "本赛季游戏",
        f"竞技：{_mode_matches(s.ranked)} 场 · 胜率 {_mode_rate(s.ranked)}",
        f"快速：{_mode_matches(s.quick)} 场 · 胜率 {_mode_rate(s.quick)}",
        f"总计：{_count(s.matches)} 场 · 胜场 {_count(s.wins)} · 胜率 {_mode_rate(ModeStats(win_rate=s.win_rate))}",
        f"竞技 K/D/A：{_count(s.ranked.kills, _count(s.kills))} / {_count(s.ranked.deaths, _count(s.deaths))} / {_count(s.ranked.assists, _count(s.assists))}",
    ]
    if s.damage is not None:
        lines.append(f"总伤害：{_fmt(s.damage)}")
    if stats.heroes:
        lines += ["", "常用英雄（快速 + 竞技总场次）"]
        for index, hero in enumerate(stats.heroes[:5], 1):
            total_matches = getattr(hero, "total_matches", getattr(hero, "matches", None))
            quick = getattr(getattr(hero, "quick", None), "matches", None)
            ranked_scope = getattr(hero, "ranked", None)
            ranked = getattr(ranked_scope, "matches", None)
            ranked_rate = getattr(ranked_scope, "win_rate", None)
            if ranked_scope is None:
                # Older adapters exposed one aggregate HeroStat.  Keep that
                # data visible while the CN adapter supplies explicit scopes.
                quick = 0
                ranked = total_matches
                ranked_rate = getattr(hero, "win_rate", None)
                if ranked_rate is None and ranked and getattr(hero, "wins", None) is not None:
                    ranked_rate = hero.wins * 100 / ranked
            lines.append(
                f"{index}. {format_hero_name(hero.hero_id, hero.hero_name)}  "
                f"总计 {_fmt(total_matches)} / 快速 {_fmt(quick)} / 竞技 {_fmt(ranked)} / 竞技胜率 {_mode_rate(ModeStats(win_rate=ranked_rate))}"
            )
    return "\n".join(lines)


def format_matches(matches: list[dict], season: str | None = None) -> str:
    title = "最近比赛" + (f"（{format_season_name(season)}的数据）" if season else "")
    if not matches:
        return title + "\n没有可用记录。"
    lines = [title]
    for item in matches[:10]:
        match_uid = str(item.get("matchUid", item.get("matchUID", item.get("id", ""))))
        player = item.get("matchPlayer", {})
        result = "胜" if player.get("isWin") == 1 else "负" if player.get("isWin") == 0 else "?"
        kda = f"{_count(player.get('k'))}/{_count(player.get('d'))}/{_count(player.get('a'))}"
        hero = format_hero_name(player.get("curHeroId")) if player.get("curHeroId") is not None else "未知英雄"
        map_name = format_match_map(item.get("matchMapId"))
        queue = format_queue(item.get("gameModeId"), item.get("playModeId"))
        map_mode = get_map_mode(item.get("matchMapId"))
        mode_text = f"{queue} / {map_mode}" if map_mode else queue
        lines.append(
            f"{result}  {_time(item.get('matchTimeStamp'))}  {hero}  KDA {kda}  "
            f"{_duration(item.get('matchPlayDuration'))}\n"
            f"地图 {map_name}  {mode_text}\n"
            f"matchUid={match_uid}"
        )
    return "\n".join(lines)


def format_match_window(report: MatchWindowReport) -> str:
    """Compact text fallback for platforms without image support."""

    total = report.total
    lines = [
        "战绩回顾",
        report.window.label,
        f"共 {_count(total.matches)} 场 · {_count(total.wins)} 胜 {_count(total.losses)} 负 · "
        f"胜率 {_fmt(total.win_rate)}%" if total.win_rate is not None else f"共 {_count(total.matches)} 场 · {_count(total.wins)} 胜 {_count(total.losses)} 负",
        f"总 K/D/A：{total.kda} · 游戏时间 {_duration(total.play_time_seconds)}",
    ]
    if not report.matches:
        lines.append("暂无对局记录")
        return "\n".join(lines)
    lines += ["", "职责表现"]
    for role in ROLE_ORDER:
        stats = report.roles.get(role, RoleWindowStats(role=role))
        label = HERO_ROLE_LABELS.get(role, role)
        if not stats.matches:
            lines.append(f"{label}：0 场 · 暂无该职责对局")
            continue
        lines.append(
            f"{label}：{stats.matches} 场 · {stats.wins} 胜 {stats.losses} 负 · 胜率 {_fmt(stats.win_rate)}%"
        )
        lines.append(
            f"K/D/A {stats.kda} · 场均击败 {_fmt(stats.average_kills)} · "
            f"场均死亡 {_fmt(stats.average_deaths)} · 场均助攻 {_fmt(stats.average_assists)}"
        )
        lines.append(
            f"场均伤害 {_fmt(stats.average_hero_damage, '数据不完整')} · "
            f"场均治疗 {_fmt(stats.average_healing, '数据不完整')} · "
            f"场均承伤 {_fmt(stats.average_damage_taken, '数据不完整')}"
        )
    lines += ["", "该时间段对局"]
    for index, match in enumerate(report.matches, 1):
        result = "胜" if match.player.is_win is True else "负" if match.player.is_win is False else "?"
        hero = _daily_hero_name(match.player.hero_id) if match.player.hero_id else "未知英雄"
        lines.append(
            f"{index:02d} {_time(match.timestamp)} {result} {hero} "
            f"{_count(match.player.kills)}/{_count(match.player.deaths)}/{_count(match.player.assists)}"
        )
    return "\n".join(lines)


def format_detail(title: str, payload: dict) -> str:
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return title + "\n接口返回了数据，但暂时没有可展示字段。"
    lines = [title]
    preferred = ("heroName", "name", "heroId", "totalMatchCount", "totalMatchWinCount", "winRate", "k", "d", "a", "totalDamage", "totalHeroDamage", "totalHeal", "totalHeroHeal")
    for key in preferred:
        if key in data and data[key] not in (None, ""):
            lines.append(f"{key}: {data[key]}")
    if len(lines) == 1:
        lines.append("接口返回了数据，但字段名还需要根据完整抓包响应映射。")
    return "\n".join(lines)


def format_hero(payload: dict, season: str | None = None) -> str:
    data = payload.get("data", payload)
    careers = data.get("careers", []) if isinstance(data, dict) else []
    if not isinstance(careers, list) or not careers:
        title = "英雄数据" + (f"（{format_season_name(season)}的数据）" if season else "")
        return title + "\n没有返回该英雄的生涯数据。"
    hero = careers[0]
    matches = hero.get("totalMatchCount")
    wins = hero.get("totalMatchWinCount")
    win_rate = wins * 100 / matches if isinstance(matches, (int, float)) and matches and isinstance(wins, (int, float)) else None
    hit_rate = hero.get("sessionMaxHitRate")
    lines = [
        f"英雄：{format_hero_name(hero.get('heroId'))}",
        *([f"（{format_season_name(season)}的数据）"] if season else []),
        f"场次：{_count(matches)}    胜场：{_count(wins)}    胜率：{_fmt(win_rate)}%",
        f"K/D/A：{_count(hero.get('k'))} / {_count(hero.get('d'))} / {_count(hero.get('a'))}",
        f"游玩时长：{_hours(hero.get('totalPlayTime'))}",
        f"英雄伤害：{_fmt(hero.get('totalHeroDamage'))}    治疗：{_fmt(hero.get('totalHeroHeal'))}",
        f"承受伤害：{_fmt(hero.get('totalDamageTaken'))}",
        f"最高命中率：{_fmt(hit_rate * 100 if isinstance(hit_rate, (int, float)) else None)}%",
        f"MVP：{_count(hero.get('totalMvpTimes'))}    SVP：{_count(hero.get('totalSvpTimes'))}",
    ]
    return "\n".join(lines)


def format_hero_result(result: HeroQueryResult) -> str:
    """Format the explicit total/quick/ranked hero model when available.

    The payload-only formatter remains public for CLI and older integrations;
    structured queries use this path so text and image output share scopes.
    """

    stats = result.stats
    if stats is None or not hasattr(stats, "ranked"):
        return format_hero(result.payload, result.season)

    total_matches = getattr(stats, "total_matches", None)
    total_wins = getattr(stats, "total_wins", None)
    total_rate = getattr(stats, "total_win_rate", None)
    quick = stats.quick
    ranked = stats.competitive
    if total_rate is None and total_matches and total_wins is not None:
        total_rate = total_wins * 100 / total_matches
    hero_name = format_hero_name(result.hero_id, result.hero_name)
    lines = [
        f"英雄：{hero_name}",
        *((f"（{format_season_name(result.season)}的数据）",) if result.season else ()),
        f"总计使用：{_count(total_matches)} 场    快速：{_count(quick.matches)} 场    竞技：{_count(ranked.matches)} 场",
        f"总计胜率：{_mode_rate(ModeStats(win_rate=total_rate))}    总胜场：{_count(total_wins)}",
        f"竞技：{_count(ranked.matches)} 场    胜场：{_count(ranked.wins)}    胜率：{_mode_rate(ranked)}",
        f"快速：{_count(quick.matches)} 场    胜场：{_count(quick.wins)}    胜率：{_mode_rate(quick)}",
        f"竞技 K/D/A：{_count(ranked.kills)} / {_count(ranked.deaths)} / {_count(ranked.assists)}",
        f"竞技 击败：{_count(ranked.kills)}    最后一击：{_count(ranked.final_hits)}    死亡：{_count(ranked.deaths)}    助攻：{_count(ranked.assists)}",
        f"竞技场均伤害：{_mode_average(ranked.hero_damage, ranked.matches)}    场均治疗：{_mode_average(ranked.heal, ranked.matches)}",
        f"竞技场均承伤：{_mode_average(ranked.damage_taken, ranked.matches)}",
        f"竞技累计伤害：{_fmt(ranked.hero_damage)}    累计治疗：{_fmt(ranked.heal)}    累计承伤：{_fmt(ranked.damage_taken)}",
        f"竞技游戏时长：{_hours(ranked.play_time_seconds)}",
        f"竞技 MVP：{_count(ranked.mvp)}    SVP：{_count(ranked.svp)}",
        f"快速 击败：{_count(quick.kills)}    最后一击：{_count(quick.final_hits)}    死亡：{_count(quick.deaths)}    助攻：{_count(quick.assists)}",
        f"快速场均伤害：{_mode_average(quick.hero_damage, quick.matches)}    场均治疗：{_mode_average(quick.heal, quick.matches)}    场均承伤：{_mode_average(quick.damage_taken, quick.matches)}",
    ]
    return "\n".join(lines)


def format_match_detail(payload: dict) -> str:
    data = payload.get("data", payload)
    matches = data.get("matches", []) if isinstance(data, dict) else []
    if not isinstance(matches, list) or not matches:
        return "对局详情\n没有返回对局数据。"
    match = matches[0]
    map_mode = get_map_mode(match.get("matchMapId"))
    lines = [
        "对局详情",
        f"时间：{_time(match.get('matchTimeStamp'))}",
        f"地图：{format_match_map(match.get('matchMapId'))}",
        f"队列：{format_queue(match.get('gameModeId'), match.get('playModeId'))}",
        f"玩法：{map_mode or format_play_mode(match.get('playModeId'))}",
        f"时长：{_duration(match.get('matchPlayDuration'))}    胜方阵营：{match.get('matchWinnerSide', '-')}",
        f"matchUid：{match.get('matchUid', '-')}",
    ]
    players = match.get("matchPlayers", [])
    if isinstance(players, list):
        camps = {p.get("camp") for p in players if isinstance(p, dict) and p.get("camp") is not None}
        for camp in sorted(camps, key=lambda value: (0, str(value).zfill(12)) if isinstance(value, (int, float)) else (1, str(value))):
            lines.append("")
            lines.append(f"阵营 {camp}")
            for player in players:
                if not isinstance(player, dict) or player.get("camp") != camp:
                    continue
                lines.append(
                    f"{'胜' if player.get('isWin') == 1 else '负'} {player.get('nickName', player.get('playerUid', '-'))} "
                    f"英雄 {format_hero_name(player.get('curHeroId'))}  {_count(player.get('k'))}/{_count(player.get('d'))}/{_count(player.get('a'))}  "
                    f"伤害 {_fmt(player.get('totalHeroDamage'))} 治疗 {_fmt(player.get('totalHeroHeal'))} 承伤 {_fmt(player.get('totalDamageTaken'))}"
                )
    return "\n".join(lines)
