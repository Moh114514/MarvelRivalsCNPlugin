"""Cross-season player specialty analysis.

The service deliberately has no QQ or rendering concerns.  It loads one
account profile, fetches explicit-mode HeroCareer snapshots in batches, joins
each season to that season's Meta rank, and only then aggregates heroes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

from ..models import PlayerHeroStats, PlayerProfile
from ..reference.heroes import HERO_ID_MAP, get_hero_id, get_hero_name
from ..reference.ranks import CN_RANK_LEVEL_MAP, get_rank_label, meta_rank_from_cn_level
from ..reference.seasons import CN_SEASON_CODES, parse_season_name, season_identity_from_cn_code
from ..datasource.base import GameMode
from .models import (
    AnalysisScope,
    CareerHeroSignature,
    HeroPerformanceAnalysis,
    HeroSeasonPerformance,
    NormalizedModeStats,
    PlayerSignatureProfile,
)
from .player_meta import PlayerMetaQueryError
from .signature_rules import (
    SIGNATURE_PRIOR_MATCHES,
    adjust_delta,
    build_signature_tags,
    calculate_confidence,
    calculate_performance_index,
    calculate_performance_sickness_score,
    calculate_play_index,
    calculate_signature_score,
    calculate_sick_score,
    calculate_weakness_index,
    classify_signature,
    classification_sort_key,
    is_sickness_candidate,
    sick_hero_sort_key,
    stability_counts,
)


logger = logging.getLogger(__name__)
SIGNATURE_CACHE_SCHEMA_VERSION = 6
SICKNESS_TOP_N = 10


class SeasonAggregationPolicy(str, Enum):
    """Interpretation of CN season snapshots."""

    INDEPENDENT = "independent"
    CUMULATIVE = "cumulative"

    @classmethod
    def parse(cls, value: str | None) -> "SeasonAggregationPolicy":
        normalized = str(value or cls.INDEPENDENT.value).strip().lower()
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError("MRCN_SIGNATURE_SEASON_POLICY 只支持 independent 或 cumulative") from exc


@dataclass(slots=True)
class _NormalizedHero:
    hero_id: str
    hero_name: str
    quick_matches: int | None
    quick_wins: int | None
    competitive_matches: int | None
    competitive_wins: int | None
    quick: NormalizedModeStats | None = None
    competitive: NormalizedModeStats | None = None

    def __post_init__(self) -> None:
        if self.quick is None:
            self.quick = NormalizedModeStats(
                matches=self.quick_matches,
                wins=self.quick_wins,
            )
        else:
            self.quick_matches = self.quick.matches
            self.quick_wins = self.quick.wins
        if self.competitive is None:
            self.competitive = NormalizedModeStats(
                matches=self.competitive_matches,
                wins=self.competitive_wins,
            )
        else:
            self.competitive_matches = self.competitive.matches
            self.competitive_wins = self.competitive.wins

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "_NormalizedHero":
        quick_value = value.get("quick")
        competitive_value = value.get("competitive")
        quick = NormalizedModeStats.from_dict(quick_value) if isinstance(quick_value, dict) else None
        competitive = (
            NormalizedModeStats.from_dict(competitive_value)
            if isinstance(competitive_value, dict) else None
        )
        return cls(
            hero_id=str(value.get("hero_id", "")),
            hero_name=str(value.get("hero_name", "未知英雄")),
            quick_matches=_optional_int(value.get("quick_matches")),
            quick_wins=_optional_int(value.get("quick_wins")),
            competitive_matches=_optional_int(value.get("competitive_matches")),
            competitive_wins=_optional_int(value.get("competitive_wins")),
            quick=quick,
            competitive=competitive,
        )


@dataclass(slots=True)
class _NormalizedSeason:
    season_code: str
    season_label: str
    heroes: dict[str, _NormalizedHero]

    def to_dict(self) -> dict[str, Any]:
        return {
            "season_code": self.season_code,
            "season_label": self.season_label,
            "heroes": {key: value.to_dict() for key, value in self.heroes.items()},
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "_NormalizedSeason":
        heroes = value.get("heroes", {})
        return cls(
            season_code=str(value.get("season_code", "")),
            season_label=str(value.get("season_label", "")),
            heroes={
                str(hero_id): _NormalizedHero.from_dict(item)
                for hero_id, item in heroes.items()
                if isinstance(item, dict)
            },
        )


class SignatureCache:
    """L1 normalized-season and L3 scope-aware analysis cache."""

    def __init__(
        self,
        root: str | Path | None,
        *,
        historical_seconds: float = 7 * 86400,
        current_seconds: float = 30 * 60,
        result_seconds: float = 15 * 60,
    ) -> None:
        self.root = Path(root) / "analysis" if root else None
        self.historical_seconds = max(0.0, float(historical_seconds))
        self.current_seconds = max(0.0, float(current_seconds))
        self.result_seconds = max(0.0, float(result_seconds))
        if self.root:
            try:
                self.root.mkdir(parents=True, exist_ok=True)
            except OSError:
                logger.warning("绝活缓存目录不可写，将仅使用内存缓存：%s", self.root)
                self.root = None

    def _path(self, prefix: str, uid: str, season: str | None = None) -> Path | None:
        if self.root is None:
            return None
        safe_season = str(season).replace(":", "_") if season is not None else None
        suffix = f"_{safe_season}" if safe_season is not None else ""
        return self.root / f"{prefix}_{uid}{suffix}.json"

    def _read(self, path: Path | None, ttl: float) -> dict[str, Any] | None:
        if path is None or ttl <= 0 or not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("schema_version") != SIGNATURE_CACHE_SCHEMA_VERSION:
                return None
            if time.time() - float(record.get("fetched_at", 0)) >= ttl:
                return None
            payload = record.get("payload")
            return payload if isinstance(payload, dict) else None
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            logger.warning("绝活缓存损坏，已忽略文件=%s", path.name if path else "unknown")
            return None

    def _write(self, path: Path | None, payload: dict[str, Any], **metadata: Any) -> None:
        if path is None:
            return
        record = {
            "schema_version": SIGNATURE_CACHE_SCHEMA_VERSION,
            "fetched_at": time.time(),
            **metadata,
            "payload": payload,
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            logger.warning("绝活缓存写入失败，已跳过文件=%s", path.name)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def load_season(self, uid: str, season: str, *, current: bool) -> _NormalizedSeason | None:
        ttl = self.current_seconds if current else self.historical_seconds
        payload = self._read(self._path("season", uid, season), ttl)
        if not payload:
            return None
        try:
            return _NormalizedSeason.from_dict(payload)
        except (AttributeError, KeyError, TypeError, ValueError):
            logger.warning("绝活赛季缓存结构无效，已忽略文件=%s", self._path("season", uid, season).name)
            return None

    def save_season(self, uid: str, season: _NormalizedSeason) -> None:
        self._write(
            self._path("season", uid, season.season_code),
            season.to_dict(),
            uid=uid,
            season=season.season_code,
        )

    def load_profile(
        self,
        uid: str,
        scope: AnalysisScope | None = None,
    ) -> PlayerSignatureProfile | None:
        scope = scope or AnalysisScope.career()
        payload = self._read(self._path("analysis", uid, scope.key), self.result_seconds)
        if not payload:
            return None
        try:
            hero_payload = payload.get("heroes", payload.get("signature_heroes", []))
            heroes = tuple(
                _signature_from_dict(item)
                for item in hero_payload
                if isinstance(item, dict)
            )
            signature_heroes = tuple(
                _signature_from_dict(item)
                for item in payload.get("signature_heroes", hero_payload)
                if isinstance(item, dict)
            )
            favorite = payload.get("favorite_hero")
            return PlayerSignatureProfile(
                uid=str(payload["uid"]),
                player_name=str(payload.get("player_name", "未知")),
                first_season=str(payload.get("first_season", "")),
                latest_season=str(payload.get("latest_season", "")),
                analyzed_seasons=tuple(str(item) for item in payload.get("analyzed_seasons", [])),
                total_matches=int(payload.get("total_matches", 0)),
                competitive_matches=int(payload.get("competitive_matches", 0)),
                meta_coverage=float(payload.get("meta_coverage", 0)),
                signature_heroes=signature_heroes,
                favorite_hero=_signature_from_dict(favorite) if isinstance(favorite, dict) else None,
                partial=bool(payload.get("partial", False)),
                failed_seasons=tuple(str(item) for item in payload.get("failed_seasons", [])),
                meta_source=str(payload.get("meta_source", "RivalsMeta")),
                meta_source_timestamp=(
                    str(payload["meta_source_timestamp"])
                    if payload.get("meta_source_timestamp") is not None else None
                ),
                meta_stale=bool(payload.get("meta_stale", False)),
                sick_heroes=tuple(
                    _signature_from_dict(item)
                    for item in payload.get("sick_heroes", [])
                    if isinstance(item, dict)
                ),
                scope=scope,
                heroes=heroes,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def save_profile(self, profile: PlayerSignatureProfile) -> None:
        scope = profile.scope or AnalysisScope.career()
        self._write(
            self._path("analysis", profile.uid, scope.key),
            _profile_to_dict(profile),
            uid=profile.uid,
            scope=scope.key,
        )


CareerAnalysisCache = SignatureCache


class PlayerCareerAnalysisService:
    """Build one shared Player × Hero analysis for every consumer."""

    def __init__(
        self,
        rivals_service,
        meta_service,
        *,
        cache_root: str | Path | None = None,
        hero_batch_size: int = 32,
        max_concurrency: int = 4,
        season_policy: SeasonAggregationPolicy | str = SeasonAggregationPolicy.INDEPENDENT,
        result_cache_seconds: float = 15 * 60,
        historical_cache_seconds: float = 7 * 86400,
        current_cache_seconds: float = 30 * 60,
    ) -> None:
        self.rivals_service = rivals_service
        self.meta_service = meta_service
        self.hero_batch_size = max(1, int(hero_batch_size))
        self.max_concurrency = max(1, int(max_concurrency))
        self.season_policy = (
            season_policy
            if isinstance(season_policy, SeasonAggregationPolicy)
            else SeasonAggregationPolicy.parse(str(season_policy))
        )
        self.cache = SignatureCache(
            cache_root,
            historical_seconds=historical_cache_seconds,
            current_seconds=current_cache_seconds,
            result_seconds=result_cache_seconds,
        )
        self._inflight: dict[str, asyncio.Task[PlayerSignatureProfile]] = {}
        self._request_semaphore: asyncio.Semaphore | None = None
        self._memory_profiles: dict[str, tuple[float, PlayerSignatureProfile]] = {}

    async def get_analysis(
        self,
        uid: str,
        scope: AnalysisScope | None = None,
    ) -> PlayerSignatureProfile:
        """Return all hero analyses for an explicit career/season scope."""

        normalized_uid = str(uid).strip()
        if not normalized_uid.isdigit():
            raise PlayerMetaQueryError("UID 必须是数字")
        if self.meta_service is None:
            raise PlayerMetaQueryError("当前未启用英雄环境功能")
        scope = self._normalize_scope(scope)
        cache_key = f"{normalized_uid}:{scope.key}"
        now = time.monotonic()
        cached = self._memory_profiles.get(cache_key)
        if cached and now - cached[0] < self.cache.result_seconds:
            return cached[1]
        disk_profile = self.cache.load_profile(normalized_uid, scope)
        if disk_profile is not None:
            self._memory_profiles[cache_key] = (now, disk_profile)
            return disk_profile

        current = self._inflight.get(cache_key)
        if current is None:
            current = asyncio.create_task(self._build_profile(normalized_uid, scope))
            self._inflight[cache_key] = current
        try:
            return await current
        finally:
            if self._inflight.get(cache_key) is current:
                self._inflight.pop(cache_key, None)

    async def get_hero_analysis(
        self,
        uid: str,
        hero_id: str | int,
        scope: AnalysisScope | None = None,
    ) -> CareerHeroSignature:
        normalized = str(hero_id).strip()
        if not normalized.isdigit():
            try:
                normalized = str(get_hero_id(normalized))
            except ValueError as exc:
                raise PlayerMetaQueryError(str(exc)) from exc
        profile = await self.get_analysis(uid, scope)
        for hero in profile.heroes:
            if str(hero.hero_id) == normalized:
                return hero
        raise PlayerMetaQueryError("未找到该英雄的可用数据")

    async def get_signature_heroes(
        self,
        uid: str,
        scope: AnalysisScope | None = None,
        *,
        top_n: int = 5,
    ) -> tuple[CareerHeroSignature, ...]:
        profile = await self.get_analysis(uid, scope)
        candidates = [hero for hero in profile.heroes if hero.signature_score > 0]
        return tuple(sorted(candidates, key=_signature_score_sort_key)[:max(1, int(top_n))])

    async def get_sick_heroes(
        self,
        uid: str,
        scope: AnalysisScope | None = None,
        *,
        top_n: int = SICKNESS_TOP_N,
    ) -> tuple[CareerHeroSignature, ...]:
        profile = await self.get_analysis(uid, scope)
        candidates = [hero for hero in profile.heroes if hero.sickness_score > 0]
        return tuple(sorted(candidates, key=sick_hero_sort_key)[:max(1, int(top_n))])

    async def get_player_signature(
        self,
        uid: str,
        *,
        top_n: int = 5,
        season: str | None = None,
    ) -> PlayerSignatureProfile:
        """Compatibility facade for the former specialty service."""

        scope = self._scope_from_season(season)
        return _limit_profile(await self.get_analysis(uid, scope), top_n)

    @staticmethod
    def _normalize_scope(scope: AnalysisScope | None) -> AnalysisScope:
        if scope is None:
            return AnalysisScope.career()
        if not isinstance(scope, AnalysisScope):
            raise TypeError("scope 必须是 AnalysisScope")
        return scope

    @staticmethod
    def _scope_from_season(season: str | None) -> AnalysisScope:
        if season is None or not str(season).strip():
            return AnalysisScope.career()
        try:
            return AnalysisScope.season(parse_season_name(str(season)))
        except ValueError as exc:
            raise PlayerMetaQueryError(str(exc)) from exc

    async def _build_profile(
        self,
        uid: str,
        scope: AnalysisScope = AnalysisScope.career(),
    ) -> PlayerSignatureProfile:
        profile = await self._get_profile_history(uid)
        all_season_codes = [
            code for _name, code in sorted(CN_SEASON_CODES.items(), key=lambda pair: int(pair[1]))
        ]
        season_codes = (
            all_season_codes
            if scope.kind == "career"
            else [str(scope.season_code)]
        )
        target_season_code = str(scope.season_code) if scope.kind == "season" else None
        baseline_season_code = None
        if self.season_policy is SeasonAggregationPolicy.CUMULATIVE and target_season_code:
            previous_codes = [
                code for code in all_season_codes
                if int(code) < int(target_season_code)
            ]
            baseline_season_code = previous_codes[-1] if previous_codes else None
            if baseline_season_code is not None:
                season_codes = [baseline_season_code, target_season_code]
        normalized_seasons: list[_NormalizedSeason] = []
        failed_seasons: list[str] = []
        partial = False

        for season_code in season_codes:
            identity = season_identity_from_cn_code(season_code)
            cached = self.cache.load_season(
                uid,
                season_code,
                current=int(season_code) == max(int(item) for item in CN_SEASON_CODES.values()),
            )
            if cached is not None:
                normalized_seasons.append(cached)
                continue
            try:
                season_data = await self._load_season(uid, season_code, identity.label)
            except Exception as exc:
                failed_seasons.append(identity.canonical_name)
                partial = True
                logger.warning("绝活赛季加载失败 season=%s error=%s", season_code, exc)
                continue
            normalized_seasons.append(season_data)
            self.cache.save_season(uid, season_data)

        loaded_codes = {season.season_code for season in normalized_seasons}
        normalized_seasons = self._apply_policy(normalized_seasons)
        if target_season_code is not None:
            if baseline_season_code is not None and baseline_season_code not in loaded_codes:
                # A cumulative target without its predecessor is not a valid
                # season delta. Avoid presenting the raw cumulative snapshot.
                partial = True
                normalized_seasons = []
            else:
                normalized_seasons = [
                    season for season in normalized_seasons
                    if season.season_code == target_season_code
                ]
        active_seasons = [
            season for season in normalized_seasons if any(
                (hero.quick_matches or 0) > 0 or (hero.competitive_matches or 0) > 0
                for hero in season.heroes.values()
            )
        ]
        meta_seasons = [
            season for season in active_seasons if any(
                (hero.competitive_matches or 0) > 0 for hero in season.heroes.values()
            )
        ]

        meta_boards: dict[str, Any] = {}
        meta_failures = 0
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def load_meta(season: _NormalizedSeason) -> None:
            nonlocal meta_failures
            rank_level = _rank_level_for(profile, season.season_code)
            rank_code = meta_rank_from_cn_level(rank_level) if rank_level is not None else None
            query_rank = rank_code or "all"
            try:
                async with semaphore:
                    meta_boards[season.season_code] = await self.meta_service.get_hero_meta_board(
                        season=season.season_code,
                        rank=query_rank,
                        sort_by="matches",
                        limit=None,
                    )
            except Exception as exc:
                meta_failures += 1
                logger.warning("绝活 Meta 加载失败 season=%s error=%s", season.season_code, exc)

        await asyncio.gather(*(load_meta(season) for season in meta_seasons))
        meta_stale = any(bool(getattr(board, "stale", False)) for board in meta_boards.values())
        partial = partial or meta_failures > 0 or meta_stale
        signatures = self._build_signatures(profile, active_seasons, meta_boards, scope=scope)
        signatures = self._add_sickness_scores(signatures, active_seasons, scope=scope)
        total_matches = sum(item.total_matches for item in signatures)
        competitive_matches = sum(item.competitive_matches for item in signatures)
        comparable_matches = sum(item.comparable_matches for item in signatures)
        meta_coverage = _coverage(comparable_matches, competitive_matches)
        analyzed = tuple(season_identity_from_cn_code(item.season_code).canonical_name for item in active_seasons)
        first = analyzed[0] if analyzed else ""
        latest = analyzed[-1] if analyzed else ""

        favorite = max(signatures, key=lambda item: item.total_matches, default=None)
        if favorite is not None and not _is_favorite_eligible(favorite):
            favorite = None
        if favorite is not None:
            signatures = [
                _with_tags(item, build_signature_tags(
                    seasons=item.seasons,
                    active_seasons=item.active_seasons,
                    competitive_matches=item.competitive_matches,
                    effective_seasons=item.effective_seasons,
                    stability=item.stability,
                    adjusted_delta=item.adjusted_delta,
                    expected_meta_win_rate=item.expected_meta_win_rate,
                    total_matches=item.total_matches,
                    is_favorite=item.hero_id == favorite.hero_id,
                ))
                for item in signatures
            ]
            favorite = next((item for item in signatures if item.hero_id == favorite.hero_id), favorite)
        sick_heroes = tuple(
            sorted(
                (
                    item for item in signatures
                    if is_sickness_candidate(
                        total_matches=item.total_matches,
                        competitive_matches=item.competitive_matches,
                        quick_matches=item.quick_matches,
                        has_win_rate=(item.actual_win_rate is not None or item.quick_win_rate is not None),
                        adjusted_delta=item.adjusted_delta,
                        comparable_matches=item.comparable_matches,
                    ) and item.sickness_score > 0
                ),
                key=sick_hero_sort_key,
        )[:SICKNESS_TOP_N]
        )
        all_heroes = tuple(signatures)
        signature_heroes = tuple(
            sorted(
                (item for item in signatures if item.signature_score > 0),
                key=_signature_score_sort_key,
            )[:5]
        )
        result = PlayerSignatureProfile(
            uid=uid,
            player_name=getattr(profile, "name", "未知") or "未知",
            first_season=first,
            latest_season=latest,
            analyzed_seasons=analyzed,
            total_matches=total_matches,
            competitive_matches=competitive_matches,
            meta_coverage=meta_coverage,
            signature_heroes=signature_heroes,
            favorite_hero=favorite,
            partial=partial,
            failed_seasons=tuple(failed_seasons),
            meta_source=next(
                (str(getattr(board, "source", "")) for board in meta_boards.values() if getattr(board, "source", None)),
                "RivalsMeta",
            ),
            meta_source_timestamp=_latest_meta_timestamp(meta_boards.values()),
            meta_stale=meta_stale,
            sick_heroes=sick_heroes,
            scope=scope,
            heroes=all_heroes,
        )
        self._memory_profiles[f"{uid}:{scope.key}"] = (time.monotonic(), result)
        self.cache.save_profile(result)
        return result

    @staticmethod
    def _add_sickness_scores(
        signatures: list[CareerHeroSignature],
        seasons: list[_NormalizedSeason] | None = None,
        *,
        scope: AnalysisScope = AnalysisScope.career(),
    ) -> list[CareerHeroSignature]:
        """Calculate the shared signed Performance/Play analysis.

        Personal baselines are computed inside each season and mode before
        being weighted across seasons.  This avoids confusing a player's
        improvement over time with a hero-specific advantage.
        """

        enriched: list[CareerHeroSignature] = []
        for item in signatures:
            personal_competitive = (
                _season_weighted_personal_delta(item.hero_id, seasons or [], "competitive")
                if seasons is not None else None
            )
            personal_quick = (
                _season_weighted_personal_delta(item.hero_id, seasons or [], "quick")
                if seasons is not None else None
            )
            play_index = calculate_play_index(
                competitive_matches=item.competitive_matches,
                quick_matches=item.quick_matches,
                usage_share=item.usage_share,
                competitive_cap=20 if scope.kind == "season" else 50,
                quick_cap=20 if scope.kind == "season" else 50,
            )
            performance_index = calculate_performance_index(
                meta_delta=item.adjusted_delta,
                personal_competitive_delta=personal_competitive,
                personal_quick_delta=personal_quick,
            )
            weakness_index = max(0.0, -performance_index)
            meta_disadvantage = (
                max(0.0, -float(item.adjusted_delta))
                if item.adjusted_delta is not None else None
            )
            sickness_candidate = is_sickness_candidate(
                total_matches=item.total_matches,
                competitive_matches=item.competitive_matches,
                quick_matches=item.quick_matches,
                has_win_rate=(item.actual_win_rate is not None or item.quick_win_rate is not None),
                adjusted_delta=item.adjusted_delta,
                comparable_matches=item.comparable_matches,
            )
            sickness_score = (
                calculate_performance_sickness_score(play_index, performance_index)
                if sickness_candidate and performance_index < 0 else 0.0
            )
            classification = item.classification if performance_index > 0 else "常用英雄"
            if performance_index > 0 and classification == "常用英雄":
                classification = "潜力绝活"
            enriched.append(
                replace(
                    item,
                    classification=classification,
                    stability=item.stability if scope.kind == "career" else None,
                    play_index=play_index,
                    weakness_index=weakness_index,
                    meta_disadvantage=meta_disadvantage,
                    personal_competitive_disadvantage=(
                        max(0.0, -personal_competitive)
                        if personal_competitive is not None else None
                    ),
                    personal_quick_disadvantage=(
                        max(0.0, -personal_quick)
                        if personal_quick is not None else None
                    ),
                    personal_competitive_delta=personal_competitive,
                    personal_quick_delta=personal_quick,
                    performance_index=performance_index,
                    signature_score=calculate_signature_score(play_index, performance_index),
                    sickness_score=sickness_score,
                    sick_score=sickness_score,
                )
            )
        return enriched

    async def _get_profile_history(self, uid: str) -> PlayerProfile:
        loader = getattr(self.rivals_service, "get_player_profile_history", None)
        if callable(loader):
            return await loader(uid)
        loader = getattr(self.rivals_service, "get_player_profile", None)
        if callable(loader):
            return await loader(uid)
        raise PlayerMetaQueryError("国服账号历史资料接口不可用")

    async def _load_season(self, uid: str, season_code: str, season_label: str) -> _NormalizedSeason:
        if self._request_semaphore is None:
            self._request_semaphore = asyncio.Semaphore(self.max_concurrency)
        hero_ids = list(HERO_ID_MAP)

        async def load_mode(mode: GameMode) -> list[PlayerHeroStats]:
            async with self._request_semaphore:
                loader = getattr(self.rivals_service, "get_hero_profiles_batch", None)
                if not callable(loader):
                    raise PlayerMetaQueryError("国服批量英雄接口不可用")
                return await loader(
                    uid,
                    hero_ids,
                    season_code,
                    mode,
                    batch_size=self.hero_batch_size,
                )

        quick_result, competitive_result = await asyncio.gather(
            load_mode(GameMode.QUICK), load_mode(GameMode.COMPETITIVE)
        )
        quick = {str(item.hero_id): item for item in quick_result}
        competitive = {str(item.hero_id): item for item in competitive_result}
        heroes: dict[str, _NormalizedHero] = {}
        for hero_id in set(quick) | set(competitive):
            quick_hero = quick.get(hero_id)
            competitive_hero = competitive.get(hero_id)
            quick_scope = _scope(quick_hero, "quick")
            competitive_scope = _scope(competitive_hero, "competitive")
            heroes[hero_id] = _NormalizedHero(
                hero_id=hero_id,
                hero_name=(getattr(competitive_hero, "hero_name", None) or getattr(quick_hero, "hero_name", None) or get_hero_name(hero_id)),
                quick_matches=quick_scope[0],
                quick_wins=quick_scope[1],
                competitive_matches=competitive_scope[0],
                competitive_wins=competitive_scope[1],
                quick=NormalizedModeStats.from_mode(quick_scope[2]),
                competitive=NormalizedModeStats.from_mode(competitive_scope[2]),
            )
        return _NormalizedSeason(season_code, season_label, heroes)

    def _apply_policy(self, seasons: list[_NormalizedSeason]) -> list[_NormalizedSeason]:
        if self.season_policy is SeasonAggregationPolicy.INDEPENDENT:
            return seasons
        previous: dict[str, _NormalizedHero] = {}
        adjusted: list[_NormalizedSeason] = []
        for season in seasons:
            current: dict[str, _NormalizedHero] = {}
            for hero_id, hero in season.heroes.items():
                old = previous.get(hero_id)
                current[hero_id] = _NormalizedHero(
                    hero_id=hero.hero_id,
                    hero_name=hero.hero_name,
                    quick_matches=_difference(hero.quick_matches, old.quick_matches if old else None),
                    quick_wins=_difference(hero.quick_wins, old.quick_wins if old else None),
                    competitive_matches=_difference(hero.competitive_matches, old.competitive_matches if old else None),
                    competitive_wins=_difference(hero.competitive_wins, old.competitive_wins if old else None),
                    quick=(hero.quick or NormalizedModeStats()).difference(old.quick if old else None),
                    competitive=(hero.competitive or NormalizedModeStats()).difference(
                        old.competitive if old else None
                    ),
                )
            # A missing hero row is not a zero cumulative snapshot. Keep the
            # last known cumulative value so a later reappearing row is
            # differenced against the correct predecessor.
            previous.update(season.heroes)
            adjusted.append(_NormalizedSeason(season.season_code, season.season_label, current))
        return adjusted

    def _build_signatures(
        self,
        profile: PlayerProfile,
        seasons: list[_NormalizedSeason],
        boards: dict[str, Any],
        *,
        scope: AnalysisScope,
    ) -> list[CareerHeroSignature]:
        hero_ids = sorted({hero_id for season in seasons for hero_id in season.heroes})
        all_matches = sum(
            max(0, int(hero.quick_matches or 0))
            + max(0, int(hero.competitive_matches or 0))
            for season in seasons for hero in season.heroes.values()
        )
        result: list[CareerHeroSignature] = []
        for hero_id in hero_ids:
            rows: list[HeroSeasonPerformance] = []
            total_matches = quick_matches = competitive_matches = 0
            quick_wins_known = True
            quick_wins_total = 0
            wins_known = True
            competitive_wins_total = 0
            comparable_matches = comparable_wins = 0
            expected_wins = 0.0
            rank_specific_matches = 0
            active = competitive = 0
            quick_stats = NormalizedModeStats()
            competitive_stats = NormalizedModeStats()
            hero_name = get_hero_name(hero_id)
            for season in seasons:
                hero = season.heroes.get(hero_id)
                if hero is None:
                    continue
                q_stats = hero.quick or NormalizedModeStats(
                    matches=hero.quick_matches, wins=hero.quick_wins
                )
                c_stats = hero.competitive or NormalizedModeStats(
                    matches=hero.competitive_matches, wins=hero.competitive_wins
                )
                quick_stats = quick_stats.add(q_stats)
                competitive_stats = competitive_stats.add(c_stats)
                q = max(0, int(q_stats.matches or 0))
                c = max(0, int(c_stats.matches or 0))
                total_matches += q + c
                quick_matches += q
                competitive_matches += c
                if q + c > 0:
                    active += 1
                if c > 0:
                    competitive += 1
                if q_stats.wins is None and q > 0:
                    quick_wins_known = False
                elif q_stats.wins is not None and q > 0:
                    quick_wins_total += max(0, int(q_stats.wins))
                if c_stats.wins is None and c > 0:
                    wins_known = False
                elif c_stats.wins is not None and c > 0:
                    competitive_wins_total += max(0, int(c_stats.wins))
                hero_name = hero.hero_name or hero_name

                rank_level = _rank_level_for(profile, season.season_code)
                rank_code = meta_rank_from_cn_level(rank_level) if rank_level is not None else None
                rank_fallback = rank_code is None
                board = boards.get(season.season_code)
                meta_result = _meta_result(board, hero_id)
                comp_wr = (
                    c_stats.wins * 100 / c
                    if c > 0 and c_stats.wins is not None
                    else None
                )
                meta_wr = getattr(meta_result, "win_rate", None)
                raw_delta = comp_wr - meta_wr if comp_wr is not None and meta_wr is not None else None
                if raw_delta is not None:
                    comparable_matches += c
                    comparable_wins += int(c_stats.wins or 0)
                    expected_wins += c * float(meta_wr) / 100
                    if not rank_fallback:
                        rank_specific_matches += c
                rows.append(HeroSeasonPerformance(
                    season_code=season.season_code,
                    season_label=season.season_label,
                    rank_level=rank_level,
                    rank_label=CN_RANK_LEVEL_MAP.get(rank_level) if rank_level is not None else None,
                    meta_rank_code=str(rank_code or "all"),
                    meta_rank_label=getattr(board, "rank_label", None) or get_rank_label(str(rank_code or "all")),
                    quick_matches=q,
                    competitive_matches=c,
                    competitive_wins=c_stats.wins,
                    competitive_win_rate=comp_wr,
                    meta_matches=getattr(meta_result, "matches", None),
                    meta_win_rate=meta_wr,
                    meta_pick_rate=getattr(meta_result, "pick_rate", None),
                    meta_ban_rate=getattr(meta_result, "ban_rate", None),
                    raw_delta=raw_delta,
                    rank_fallback=rank_fallback,
                    meta_available=meta_result is not None,
                ))
            if total_matches <= 0:
                continue
            comparable_actual = comparable_wins * 100 / comparable_matches if comparable_matches else None
            actual = (
                competitive_wins_total * 100 / competitive_matches
                if wins_known and competitive_matches
                else None
            )
            expected = expected_wins * 100 / comparable_matches if comparable_matches else None
            raw_delta = (
                comparable_actual - expected
                if comparable_actual is not None and expected is not None
                else None
            )
            adjusted = adjust_delta(raw_delta, comparable_matches, SIGNATURE_PRIOR_MATCHES)
            stability, effective, positive = stability_counts(rows)
            comparable_seasons = sum(1 for row in rows if row.raw_delta is not None)
            meta_coverage = _coverage(comparable_matches, competitive_matches)
            rank_coverage = _coverage(rank_specific_matches, competitive_matches)
            classification = classify_signature(
                competitive_matches=comparable_matches,
                effective_seasons=effective,
                raw_delta=raw_delta,
                adjusted_delta=adjusted,
                stability=stability,
                # A full-rank fallback is usable data, but it is not the
                # same evidence as a same-rank comparison for classification.
                meta_coverage=min(meta_coverage, rank_coverage),
            )
            result.append(HeroPerformanceAnalysis(
                hero_id=hero_id,
                hero_name=hero_name,
                total_matches=total_matches,
                quick_matches=quick_matches,
                competitive_matches=competitive_matches,
                competitive_wins=competitive_wins_total if wins_known else None,
                usage_share=total_matches * 100 / max(1, all_matches),
                actual_win_rate=actual,
                expected_meta_win_rate=expected,
                raw_delta=raw_delta,
                adjusted_delta=adjusted,
                active_seasons=active,
                competitive_seasons=competitive,
                comparable_seasons=comparable_seasons,
                effective_seasons=effective,
                positive_seasons=positive,
                stability=stability,
                comparable_matches=comparable_matches,
                meta_coverage=meta_coverage,
                rank_specific_coverage=rank_coverage,
                confidence=calculate_confidence(comparable_matches, meta_coverage, rank_coverage),
                classification=classification,
                tags=(),
                seasons=tuple(rows),
                quick_wins=quick_wins_total if quick_wins_known else None,
                quick_win_rate=(
                    quick_wins_total * 100 / quick_matches
                    if quick_wins_known and quick_matches
                    else None
                ),
                scope=scope,
                quick_stats=quick_stats,
                competitive_stats=competitive_stats,
                meta_delta=raw_delta,
                adjusted_meta_delta=adjusted,
            ))
        return result


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _difference(current: int | None, previous: int | None) -> int | None:
    if current is None:
        return None
    if previous is None:
        return max(0, int(current))
    return max(0, int(current) - int(previous))


def _scope(
    hero: PlayerHeroStats | None,
    scope_name: str,
) -> tuple[int | None, int | None, Any | None]:
    if hero is None:
        return None, None, None
    scope = getattr(hero, scope_name, None)
    if scope is None and scope_name == "competitive":
        scope = getattr(hero, "ranked", None)
    if scope is None:
        return None, None, None
    return (
        _optional_int(getattr(scope, "matches", None)),
        _optional_int(getattr(scope, "wins", None)),
        scope,
    )


def _rank_level_for(profile: PlayerProfile, season_code: str) -> int | None:
    history = getattr(profile, "rank_history", {}) or {}
    value = history.get(str(season_code))
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _meta_result(board: Any, hero_id: str) -> Any | None:
    if board is None:
        return None
    for item in getattr(board, "heroes", ()):
        if str(getattr(item, "hero_id", "")) == str(hero_id):
            return item
    return None


def _coverage(numerator: int, denominator: int) -> float:
    return numerator * 100 / denominator if denominator else 0.0


def _season_weighted_personal_delta(
    hero_id: str,
    seasons: list[_NormalizedSeason],
    mode_name: str,
) -> float | None:
    """Compare a hero with same-season, same-mode leave-one-out baselines."""

    weighted_delta = 0.0
    weighted_matches = 0
    for season in seasons:
        hero = season.heroes.get(hero_id)
        if hero is None:
            continue
        current = getattr(hero, mode_name, None) or NormalizedModeStats()
        matches = int(current.matches or 0)
        if matches <= 0 or current.wins is None:
            continue
        other_matches = 0
        other_wins = 0
        for other_id, other in season.heroes.items():
            if other_id == hero_id:
                continue
            stats = getattr(other, mode_name, None) or NormalizedModeStats()
            candidate_matches = int(stats.matches or 0)
            if candidate_matches <= 0 or stats.wins is None:
                continue
            other_matches += candidate_matches
            other_wins += max(0, int(stats.wins))
        if other_matches <= 0:
            continue
        current_rate = float(current.wins) * 100 / matches
        baseline_rate = other_wins * 100 / other_matches
        weighted_delta += (current_rate - baseline_rate) * matches
        weighted_matches += matches
    if weighted_matches <= 0:
        return None
    return weighted_delta / weighted_matches


def _leave_one_out_disadvantage(
    item: CareerHeroSignature,
    signatures: list[CareerHeroSignature],
    *,
    matches_attr: str,
    wins_attr: str,
    rate_attr: str,
) -> float | None:
    """Compare a hero with the player's other heroes in the same mode."""

    item_rate = getattr(item, rate_attr, None)
    item_matches = int(getattr(item, matches_attr, 0) or 0)
    item_wins = getattr(item, wins_attr, None)
    if item_rate is None or item_matches <= 0 or item_wins is None:
        return None
    other_matches = 0
    other_wins = 0
    for other in signatures:
        if other.hero_id == item.hero_id:
            continue
        matches = int(getattr(other, matches_attr, 0) or 0)
        wins = getattr(other, wins_attr, None)
        if matches <= 0 or wins is None:
            continue
        other_matches += matches
        other_wins += max(0, int(wins))
    if other_matches <= 0:
        return None
    baseline = other_wins * 100 / other_matches
    return max(0.0, baseline - float(item_rate))


def _is_favorite_eligible(item: CareerHeroSignature) -> bool:
    return item.total_matches >= 30 or item.usage_share >= 20


def _with_tags(item: CareerHeroSignature, tags: tuple[str, ...]) -> CareerHeroSignature:
    return replace(item, tags=tags)


def _signature_from_dict(value: dict[str, Any]) -> CareerHeroSignature:
    seasons = tuple(HeroSeasonPerformance(**item) for item in value.get("seasons", []) if isinstance(item, dict))
    data = dict(value)
    data["tags"] = tuple(data.get("tags", ()))
    data["seasons"] = seasons
    if isinstance(data.get("scope"), dict):
        data["scope"] = AnalysisScope(**data["scope"])
    for field_name in ("quick_stats", "competitive_stats"):
        if isinstance(data.get(field_name), dict):
            data[field_name] = NormalizedModeStats(**data[field_name])
    return HeroPerformanceAnalysis(**data)


def _profile_to_dict(profile: PlayerSignatureProfile) -> dict[str, Any]:
    return {
        "uid": profile.uid,
        "player_name": profile.player_name,
        "first_season": profile.first_season,
        "latest_season": profile.latest_season,
        "analyzed_seasons": list(profile.analyzed_seasons),
        "total_matches": profile.total_matches,
        "competitive_matches": profile.competitive_matches,
        "meta_coverage": profile.meta_coverage,
        "signature_heroes": [asdict(item) for item in profile.signature_heroes],
        "favorite_hero": asdict(profile.favorite_hero) if profile.favorite_hero else None,
        "partial": profile.partial,
        "failed_seasons": list(profile.failed_seasons),
        "meta_source": profile.meta_source,
        "meta_source_timestamp": profile.meta_source_timestamp,
        "meta_stale": profile.meta_stale,
        "sick_heroes": [asdict(item) for item in profile.sick_heroes],
        "scope": asdict(profile.scope or AnalysisScope.career()),
        "heroes": [asdict(item) for item in (profile.heroes or profile.signature_heroes)],
    }


def _latest_meta_timestamp(boards: Any) -> str | None:
    values: list[str] = []
    for board in boards:
        timestamp = getattr(board, "source_timestamp", None)
        if timestamp is None:
            continue
        if hasattr(timestamp, "isoformat"):
            values.append(timestamp.isoformat())
        else:
            values.append(str(timestamp))
    return max(values) if values else None


def _limit_profile(profile: PlayerSignatureProfile, top_n: int) -> PlayerSignatureProfile:
    if len(profile.signature_heroes) <= top_n:
        return profile
    return replace(profile, signature_heroes=profile.signature_heroes[:top_n])


def _signature_score_sort_key(item: Any) -> tuple[float, float, int]:
    return (
        -float(getattr(item, "signature_score", 0.0) or 0.0),
        -float(getattr(item, "performance_index", 0.0) or 0.0),
        -int(getattr(item, "total_matches", 0) or 0),
    )


__all__ = [
    "AnalysisScope",
    "CareerAnalysisCache",
    "PlayerCareerAnalysisService",
    "PlayerSignatureService",
    "SeasonAggregationPolicy",
    "SIGNATURE_CACHE_SCHEMA_VERSION",
    "SICKNESS_TOP_N",
    "SignatureCache",
]


# Compatibility name retained for integrations and older plugins.
PlayerSignatureService = PlayerCareerAnalysisService
