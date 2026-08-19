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
from ..reference.heroes import HERO_ID_MAP, get_hero_name
from ..reference.ranks import CN_RANK_LEVEL_MAP, get_rank_label, meta_rank_from_cn_level
from ..reference.seasons import CN_SEASON_CODES, season_identity_from_cn_code
from ..datasource.base import GameMode
from .models import CareerHeroSignature, HeroSeasonPerformance, PlayerSignatureProfile
from .player_meta import PlayerMetaQueryError
from .signature_rules import (
    SIGNATURE_PRIOR_MATCHES,
    adjust_delta,
    build_signature_tags,
    calculate_confidence,
    calculate_sick_score,
    classify_signature,
    classification_sort_key,
    sick_hero_sort_key,
    stability_counts,
)


logger = logging.getLogger(__name__)
SIGNATURE_CACHE_SCHEMA_VERSION = 4
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "_NormalizedHero":
        return cls(
            hero_id=str(value.get("hero_id", "")),
            hero_name=str(value.get("hero_name", "未知英雄")),
            quick_matches=_optional_int(value.get("quick_matches")),
            quick_wins=_optional_int(value.get("quick_wins")),
            competitive_matches=_optional_int(value.get("competitive_matches")),
            competitive_wins=_optional_int(value.get("competitive_wins")),
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
    """Small JSON cache for normalized season data and final profiles."""

    def __init__(
        self,
        root: str | Path | None,
        *,
        historical_seconds: float = 7 * 86400,
        current_seconds: float = 30 * 60,
        result_seconds: float = 15 * 60,
    ) -> None:
        self.root = Path(root) / "signature" if root else None
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
        suffix = f"_{season}" if season is not None else ""
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
        return _NormalizedSeason.from_dict(payload) if payload else None

    def save_season(self, uid: str, season: _NormalizedSeason) -> None:
        self._write(
            self._path("season", uid, season.season_code),
            season.to_dict(),
            uid=uid,
            season=season.season_code,
        )

    def load_profile(self, uid: str) -> PlayerSignatureProfile | None:
        payload = self._read(self._path("profile", uid), self.result_seconds)
        if not payload:
            return None
        try:
            heroes = tuple(
                _signature_from_dict(item)
                for item in payload.get("signature_heroes", [])
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
                signature_heroes=heroes,
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
            )
        except (KeyError, TypeError, ValueError):
            return None

    def save_profile(self, profile: PlayerSignatureProfile) -> None:
        self._write(self._path("profile", profile.uid), _profile_to_dict(profile), uid=profile.uid)


class PlayerSignatureService:
    """Build a cross-season signature without changing PlayerMetaService."""

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

    async def get_player_signature(self, uid: str, *, top_n: int = 5) -> PlayerSignatureProfile:
        normalized_uid = str(uid).strip()
        if not normalized_uid.isdigit():
            raise PlayerMetaQueryError("UID 必须是数字")
        if self.meta_service is None:
            raise PlayerMetaQueryError("当前未启用英雄环境功能")
        top_n = max(1, int(top_n))
        now = time.monotonic()
        cached = self._memory_profiles.get(normalized_uid)
        if cached and now - cached[0] < self.cache.result_seconds:
            return _limit_profile(cached[1], top_n)
        disk_profile = self.cache.load_profile(normalized_uid)
        if disk_profile is not None:
            self._memory_profiles[normalized_uid] = (now, disk_profile)
            return _limit_profile(disk_profile, top_n)

        current = self._inflight.get(normalized_uid)
        if current is None:
            current = asyncio.create_task(self._build_profile(normalized_uid))
            self._inflight[normalized_uid] = current
        try:
            profile = await current
            return _limit_profile(profile, top_n)
        finally:
            if self._inflight.get(normalized_uid) is current:
                self._inflight.pop(normalized_uid, None)

    async def _build_profile(self, uid: str) -> PlayerSignatureProfile:
        profile = await self._get_profile_history(uid)
        season_codes = [code for _name, code in sorted(CN_SEASON_CODES.items(), key=lambda pair: int(pair[1]))]
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

        normalized_seasons = self._apply_policy(normalized_seasons)
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
        signatures = self._build_signatures(profile, active_seasons, meta_boards)
        signatures = [
            replace(
                item,
                sick_score=calculate_sick_score(
                    actual_win_rate=item.actual_win_rate,
                    competitive_matches=item.comparable_matches,
                    adjusted_delta=item.adjusted_delta,
                    meta_coverage=item.meta_coverage,
                    rank_specific_coverage=item.rank_specific_coverage,
                    classification=item.classification,
                ),
            )
            for item in signatures
        ]
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
                (item for item in signatures if item.sick_score > 0),
                key=sick_hero_sort_key,
        )[:SICKNESS_TOP_N]
        )
        signatures.sort(key=classification_sort_key)
        result = PlayerSignatureProfile(
            uid=uid,
            player_name=getattr(profile, "name", "未知") or "未知",
            first_season=first,
            latest_season=latest,
            analyzed_seasons=analyzed,
            total_matches=total_matches,
            competitive_matches=competitive_matches,
            meta_coverage=meta_coverage,
            signature_heroes=tuple(signatures[:5]),
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
        )
        self._memory_profiles[uid] = (time.monotonic(), result)
        self.cache.save_profile(result)
        return result

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
    ) -> list[CareerHeroSignature]:
        hero_ids = sorted({hero_id for season in seasons for hero_id in season.heroes})
        all_competitive = sum(
            max(0, int(hero.competitive_matches or 0))
            for season in seasons for hero in season.heroes.values()
        )
        result: list[CareerHeroSignature] = []
        for hero_id in hero_ids:
            rows: list[HeroSeasonPerformance] = []
            total_matches = quick_matches = competitive_matches = 0
            wins_known = True
            competitive_wins_total = 0
            comparable_matches = comparable_wins = 0
            expected_wins = 0.0
            rank_specific_matches = 0
            active = competitive = 0
            hero_name = get_hero_name(hero_id)
            for season in seasons:
                hero = season.heroes.get(hero_id)
                if hero is None:
                    continue
                q = max(0, int(hero.quick_matches or 0))
                c = max(0, int(hero.competitive_matches or 0))
                total_matches += q + c
                quick_matches += q
                competitive_matches += c
                if q + c > 0:
                    active += 1
                if c > 0:
                    competitive += 1
                if hero.competitive_wins is None and c > 0:
                    wins_known = False
                elif hero.competitive_wins is not None and c > 0:
                    competitive_wins_total += max(0, int(hero.competitive_wins))
                hero_name = hero.hero_name or hero_name

                rank_level = _rank_level_for(profile, season.season_code)
                rank_code = meta_rank_from_cn_level(rank_level) if rank_level is not None else None
                rank_fallback = rank_code is None
                board = boards.get(season.season_code)
                meta_result = _meta_result(board, hero_id)
                comp_wr = (
                    hero.competitive_wins * 100 / c
                    if c > 0 and hero.competitive_wins is not None
                    else None
                )
                meta_wr = getattr(meta_result, "win_rate", None)
                raw_delta = comp_wr - meta_wr if comp_wr is not None and meta_wr is not None else None
                if raw_delta is not None:
                    comparable_matches += c
                    comparable_wins += int(hero.competitive_wins or 0)
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
                    competitive_wins=hero.competitive_wins,
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
            result.append(CareerHeroSignature(
                hero_id=hero_id,
                hero_name=hero_name,
                total_matches=total_matches,
                quick_matches=quick_matches,
                competitive_matches=competitive_matches,
                competitive_wins=competitive_wins_total if wins_known else None,
                usage_share=total_matches * 100 / max(1, sum(
                    max(0, int(item.quick_matches or 0)) + max(0, int(item.competitive_matches or 0))
                    for season in seasons for item in season.heroes.values()
                )),
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


def _scope(hero: PlayerHeroStats | None, scope_name: str) -> tuple[int | None, int | None]:
    if hero is None:
        return None, None
    scope = getattr(hero, scope_name, None)
    if scope is None and scope_name == "competitive":
        scope = getattr(hero, "ranked", None)
    if scope is None:
        return None, None
    return _optional_int(getattr(scope, "matches", None)), _optional_int(getattr(scope, "wins", None))


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


def _is_favorite_eligible(item: CareerHeroSignature) -> bool:
    return item.total_matches >= 30 or item.usage_share >= 20


def _with_tags(item: CareerHeroSignature, tags: tuple[str, ...]) -> CareerHeroSignature:
    return CareerHeroSignature(**{**asdict(item), "tags": tags, "seasons": item.seasons})


def _signature_from_dict(value: dict[str, Any]) -> CareerHeroSignature:
    seasons = tuple(HeroSeasonPerformance(**item) for item in value.get("seasons", []) if isinstance(item, dict))
    data = dict(value)
    data["tags"] = tuple(data.get("tags", ()))
    data["seasons"] = seasons
    return CareerHeroSignature(**data)


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


__all__ = [
    "PlayerSignatureService",
    "SeasonAggregationPolicy",
    "SIGNATURE_CACHE_SCHEMA_VERSION",
    "SICKNESS_TOP_N",
    "SignatureCache",
]
