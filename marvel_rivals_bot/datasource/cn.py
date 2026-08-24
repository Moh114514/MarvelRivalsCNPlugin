from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import Mapping
from typing import Any

import httpx

from ..reference.heroes import get_hero_name
from ..reference.ranks import CN_RANK_LEVEL_MAP
from ..models import CareerSummary, MatchSummaryPage, ModeStats, PlayerHeroStats, PlayerProfile, PlayerStats, RecentMatch
from .base import DEFAULT_PLAY_MODE, DataSourceError, GameMode, RivalsDataSource


# Compatibility name: CN's detailed API levels remain distinct from Meta's
# broad rank buckets.
RANK_LEVEL_MAP = CN_RANK_LEVEL_MAP
logger = logging.getLogger(__name__)


def _number(data: Mapping[str, Any], *keys: str) -> int | float | None:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            try:
                if isinstance(value, float):
                    return value
                return float(value) if isinstance(value, str) and "." in value else int(value)
            except (TypeError, ValueError):
                continue
    return None


def _count(data: Mapping[str, Any], *keys: str) -> int | None:
    value = _number(data, *keys)
    return round(value) if value is not None else None


def _text(data: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return str(value)
    return default


def _dynamic_fields(data: Mapping[str, Any], *keys: str) -> dict[str, float]:
    """Read numeric DynamicFields without assigning them business meaning."""

    for key in keys:
        value = data.get(key)
        if not isinstance(value, Mapping):
            continue
        result: dict[str, float] = {}
        for feature_key, feature_value in value.items():
            try:
                if isinstance(feature_value, bool) or feature_value in (None, ""):
                    continue
                result[str(feature_key)] = float(feature_value)
            except (TypeError, ValueError):
                continue
        return result
    return {}


def _first_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                return dict(item)
    return {}


def _career_mapping(value: Any) -> dict[str, Any]:
    """Return the aggregate career row from observed loadCareer shapes."""
    outer = _first_mapping(value)
    rows = outer.get("careers")
    if isinstance(rows, list):
        row = _first_mapping(rows)
        if row:
            return {**outer, **row}
    career = outer.get("career")
    if isinstance(career, Mapping):
        return {**outer, **career}
    return outer


def _mode_stats(value: Any) -> ModeStats:
    data = _career_mapping(value)
    raw_matches = _number(
        data,
        "totalMatchCount", "matchCount", "matches", "totalMatches",
        "totalMatchNum", "matchNum", "gameCount", "totalGameCount",
        "battleCount", "totalBattleCount", "playCount", "totalPlayCount",
        "useCount", "totalUseCount",
    )
    matches = _number(
        data,
        "totalMatchCount", "matchCount", "matches", "totalMatches",
        "totalMatchNum", "matchNum", "gameCount", "totalGameCount",
        "battleCount", "totalBattleCount", "playCount", "totalPlayCount",
        "useCount", "totalUseCount",
    )
    effective_matches = _number(data, "effectiveMatches", "effectiveMatchCount")
    if effective_matches is None:
        effective_matches = raw_matches
    raw_wins = _number(
        data,
        "totalMatchWinCount", "totalWinCount", "winCount", "wins",
        "totalWinNum", "winNum", "gameWinCount", "totalGameWinCount",
    )
    wins = raw_wins
    effective_wins = _number(data, "effectiveWins", "effectiveWinCount")
    if effective_wins is None:
        effective_wins = raw_wins
    win_rate = _number(data, "winRate")
    if win_rate is None and effective_matches and effective_wins is not None:
        win_rate = effective_wins * 100 / effective_matches
    return ModeStats(
        matches=round(matches) if matches is not None else None,
        effective_matches=float(effective_matches) if effective_matches is not None else None,
        wins=round(wins) if wins is not None else None,
        effective_wins=float(effective_wins) if effective_wins is not None else None,
        kills=_count(data, "k", "kills", "totalKill"),
        deaths=_count(data, "d", "deaths", "totalDeath"),
        assists=_count(data, "a", "assists", "totalAssist"),
        final_hits=_count(data, "lastKill"),
        solo_eliminations=_count(data, "soloKill", "soloKills", "soloEliminations"),
        critical_eliminations=_count(data, "headKill", "criticalKill", "criticalEliminations"),
        main_attack_count=_count(data, "mainAttackCnt", "mainAttackCount"),
        main_attack_hits=_count(data, "mainAttackHit", "mainAttackHits"),
        max_kills=_count(data, "sessionMaxK"),
        max_assists=_count(data, "sessionMaxA"),
        max_final_hits=_count(data, "sessionMaxLastKill"),
        win_rate=win_rate,
        damage=_count(data, "totalDamage", "damage"),
        hero_damage=_count(data, "totalHeroDamage", "heroDamage"),
        heal=_count(data, "totalHeroHeal", "totalHeal", "heroHeal", "heal"),
        damage_taken=_count(data, "totalDamageTaken", "damageTaken"),
        hit_rate=_number(data, "sessionMaxHitRate", "hitRate"),
        play_time_seconds=_number(data, "totalPlayTime", "playTime"),
        mvp=_count(data, "totalMvpTimes", "mvp", "mvpTimes"),
        svp=_count(data, "totalSvpTimes", "svp", "svpTimes"),
        dynamic_sum=_dynamic_fields(data, "sumDynamicFields", "sum_dynamic_fields"),
        dynamic_max=_dynamic_fields(data, "maxDynamicFields", "max_dynamic_fields"),
    )


def _mode_stats_is_empty(value: ModeStats) -> bool:
    return all(
        getattr(value, field_name) is None or getattr(value, field_name) == {}
        for field_name in ModeStats.__dataclass_fields__
    )


def _rank_level(value: Any, season: str = "19") -> int | None:
    try:
        return _rank_levels(value).get(str(int(season)))
    except (TypeError, ValueError):
        return None


def _rank_levels(value: Any) -> dict[str, int]:
    """Parse CN ``rankGameSeason`` into ``season_code -> rank_level``."""

    if not isinstance(value, (str, Mapping)) or not value:
        return {}
    try:
        seasons = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(seasons, Mapping):
        return {}

    result: dict[str, int] = {}
    for key, raw_rank in seasons.items():
        key_text = str(key)
        if key_text.startswith("10010") and key_text[5:].isdigit():
            season_code = str(int(key_text[5:]))
        elif key_text.isdigit():
            season_code = str(int(key_text))
        else:
            continue
        try:
            rank = json.loads(raw_rank) if isinstance(raw_rank, str) else raw_rank
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(rank, Mapping):
            continue
        level = _number(rank, "level")
        if level is not None:
            result[season_code] = int(level)
    return result


def _rank_scores(value: Any) -> dict[str, int]:
    """Parse CN ``rankGameSeason`` into ``season_code -> rank score``."""

    if not isinstance(value, (str, Mapping)) or not value:
        return {}
    try:
        seasons = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(seasons, Mapping):
        return {}

    result: dict[str, int] = {}
    for key, raw_rank in seasons.items():
        key_text = str(key)
        if key_text.startswith("10010") and key_text[5:].isdigit():
            season_code = str(int(key_text[5:]))
        elif key_text.isdigit():
            season_code = str(int(key_text))
        else:
            continue
        try:
            rank = json.loads(raw_rank) if isinstance(raw_rank, str) else raw_rank
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(rank, Mapping):
            continue
        score = _number(rank, "rank_score", "rankScore", "score")
        if score is not None:
            result[season_code] = int(round(score))
    return result


def _rank_text(value: Any, season: str = "19") -> str:
    if not isinstance(value, (str, Mapping)) or not value:
        return ""
    try:
        seasons = json.loads(value) if isinstance(value, str) else value
        if isinstance(seasons, Mapping):
            season_code = str(int(season))
            current = seasons.get(f"10010{int(season):02d}", seasons.get(season_code))
        else:
            current = None
        rank = json.loads(current) if isinstance(current, str) else current
    except (json.JSONDecodeError, TypeError):
        return value
    if not isinstance(rank, dict):
        return ""
    level = _number(rank, "level")
    score = _number(rank, "rank_score")
    if level is None:
        return ""
    rank_name = RANK_LEVEL_MAP.get(int(level), f"等级 {int(level)}")
    return rank_name + (f"（{int(score)} 分）" if score is not None else "")


class CNDataSource(RivalsDataSource):
    """Adapter for the CN mini-program API observed in mitmproxy.

    The capture established endpoint names, but not a stable public contract.
    Request body and headers are therefore configurable rather than guessed in
    the plugin. This also keeps short-lived credentials out of source control.
    """

    DEFAULT_PATHS = {
        "role": "/api/role/loadByRoleId",
        "data": "/api/game/player/loadData",
        "summary": "/api/game/player/loadSummary",
        "summary_detail": "/api/game/player/loadSummaryDetail",
        "career": "/api/game/player/loadCareer",
        "hero": "/api/game/player/loadHeroCareer",
        "sort_hero": "/api/game/player/loadSortHero",
        "matches": "/api/game/player/loadSummary",
    }

    DEFAULT_BODY_TEMPLATES = {
        "data": '{"playerUid":{player_uid}}',
        "summary": '{"matchSeason":{"$eq":"{season}"},"gameModeId":{"$in":[1,2,4]},"playModeId":{"$in":[0,7,8]},"page":0,"pageSize":3,"playerUid":{player_uid}}',
        "summary_detail": '{"matchUids":{match_uids}}',
        # The three captured endpoints use scalar mode fields.  Keep the
        # placeholders configurable, but do not silently turn a single-mode
        # request back into a mixed $in query.
        "career": '{"matchSeason":"{season}","gameModeId":{game_mode_id},"playModeId":{play_mode_id},"playerUid":{player_uid}}',
        "career_quick": '{"matchSeason":"{season}","gameModeId":1,"playModeId":0,"playerUid":{player_uid}}',
        "career_ranked": '{"matchSeason":"{season}","gameModeId":2,"playModeId":0,"playerUid":{player_uid}}',
        "career_competitive": '{"matchSeason":"{season}","gameModeId":2,"playModeId":0,"playerUid":{player_uid}}',
        "hero": '{"heroIdList":{hero_ids},"matchSeason":"{season}","gameModeId":{game_mode_id},"playModeId":{play_mode_id},"playerUid":{player_uid}}',
        "hero_quick": '{"heroIdList":{hero_ids},"matchSeason":"{season}","gameModeId":1,"playModeId":0,"playerUid":{player_uid}}',
        "hero_ranked": '{"heroIdList":{hero_ids},"matchSeason":"{season}","gameModeId":2,"playModeId":0,"playerUid":{player_uid}}',
        "hero_competitive": '{"heroIdList":{hero_ids},"matchSeason":"{season}","gameModeId":2,"playModeId":0,"playerUid":{player_uid}}',
        "sort_hero": '{"matchSeason":"{season}","gameModeId":{game_mode_id},"playModeId":{play_mode_id},"playerUid":{player_uid}}',
        "sort_hero_quick": '{"matchSeason":"{season}","gameModeId":1,"playModeId":0,"playerUid":{player_uid}}',
        "sort_hero_ranked": '{"matchSeason":"{season}","gameModeId":2,"playModeId":0,"playerUid":{player_uid}}',
        "sort_hero_competitive": '{"matchSeason":"{season}","gameModeId":2,"playModeId":0,"playerUid":{player_uid}}',
        "matches": '{"matchSeason":{"$eq":"{season}"},"gameModeId":{"$in":[1,2,4]},"playModeId":{"$in":[0,7,8]},"page":0,"pageSize":10,"playerUid":{player_uid}}',
    }
    PRIVATE_PROFILE_MESSAGES = (
        "不允许查看该用户的游戏数据",
        "不允许查看该用户游戏数据",
    )
    PRIVATE_PROFILE_HINT = "请前往“漫威争锋小程序→战绩→设置”打开查询权限。"

    def __init__(self, *, client: httpx.AsyncClient | None = None, env: Mapping[str, Any] | None = None):
        config = os.environ if env is None else env
        base_url = config.get("MRCN_API_BASE_URL", "").strip().rstrip("/")
        if not base_url:
            raise DataSourceError("未配置 MRCN_API_BASE_URL，请先填写官方小程序接口前缀")
        self.base_url = base_url
        self.timeout = float(config.get("MRCN_TIMEOUT_SECONDS", "10"))
        self.mode_cache_seconds = max(0.0, float(config.get("MRCN_CACHE_SECONDS", "60")))
        self._mode_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self.default_season = self._normalize_season(config.get("MRCN_DEFAULT_SEASON", "19"))
        self.debug = str(config.get("MRCN_DEBUG", "0")).lower() in {"1", "true", "yes"}
        verify_value = str(config.get("MRCN_VERIFY_SSL", "true")).lower()
        self.verify_ssl: bool | str = verify_value not in {"0", "false", "no"}
        ca_cert = str(config.get("MRCN_CA_CERT", "")).strip()
        if ca_cert:
            self.verify_ssl = ca_cert
        self.proxy = str(config.get("MRCN_PROXY", "")).strip() or None
        self.trust_env = str(config.get("MRCN_TRUST_ENV", "false")).lower() in {"1", "true", "yes"}
        self.body_template = config.get("MRCN_REQUEST_BODY_TEMPLATE", '{"roleId":"{uid}"}')
        try:
            configured_headers = config.get("MRCN_HEADERS_JSON", "{}")
            self.headers = configured_headers if isinstance(configured_headers, dict) else json.loads(configured_headers)
        except json.JSONDecodeError as exc:
            raise DataSourceError("MRCN_HEADERS_JSON 不是有效 JSON") from exc
        access_token = str(config.get("MRCN_ACCESS_TOKEN", "")).strip()
        if access_token:
            self.headers["access_token"] = access_token
        self.paths = dict(self.DEFAULT_PATHS)
        for name in self.paths:
            self.paths[name] = config.get(f"MRCN_{name.upper()}_PATH", self.paths[name]).strip()
        generic_template = config.get("MRCN_REQUEST_BODY_TEMPLATE")
        self.body_templates = {
            name: config.get(
                f"MRCN_{name.upper()}_BODY_TEMPLATE",
                generic_template if generic_template is not None else self.DEFAULT_BODY_TEMPLATES.get(name, self.body_template),
            )
            for name in self.paths
        }
        # Mode-specific templates are deliberately separate from the legacy
        # aggregate templates.  The CN API is observed and unstable, so each
        # scope remains configurable without changing the source abstraction.
        for name in (
            "career_quick", "career_ranked", "career_competitive",
            "hero_quick", "hero_ranked", "hero_competitive",
            "sort_hero_quick", "sort_hero_ranked", "sort_hero_competitive",
        ):
            self.body_templates[name] = config.get(
                f"MRCN_{name.upper()}_BODY_TEMPLATE",
                self.DEFAULT_BODY_TEMPLATES[name],
            )
        legacy_templates = {
            "data": "{}",
            "career": '{"matchSeason":"19"}',
            "hero": '{"heroIdList":{hero_ids},"matchSeason":"19"}',
            "sort_hero": '{"matchSeason":"19"}',
        }
        for name, legacy in legacy_templates.items():
            if self.body_templates.get(name) == legacy:
                self.body_templates[name] = self.DEFAULT_BODY_TEMPLATES[name]
        for name in (
            "summary", "career", "career_quick", "career_ranked", "career_competitive",
            "hero", "hero_quick", "hero_ranked", "hero_competitive",
            "sort_hero", "sort_hero_quick", "sort_hero_ranked", "sort_hero_competitive", "matches",
        ):
            template = self.body_templates.get(name, "")
            self.body_templates[name] = template.replace('"matchSeason":"19"', '"matchSeason":"{season}"').replace(
                '"$eq":"19"', '"$eq":"{season}"'
            )
        for name in ("summary", "matches"):
            template = self.body_templates.get(name, "")
            if "{player_uid}" not in template and '"page"' in template:
                body = json.loads(template)
                body["playerUid"] = "__PLAYER_UID__"
                template = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
                self.body_templates[name] = template.replace('"__PLAYER_UID__"', "{player_uid}")
        detail_template = self.body_templates.get("summary_detail", "")
        if '"matchUids":["{match_uid}"]' in detail_template:
            self.body_templates["summary_detail"] = detail_template.replace(
                '"matchUids":["{match_uid}"]', '"matchUids":{match_uids}'
            )
        self._client = client
        self._owned_client: httpx.AsyncClient | None = None

    def _request_client(self) -> httpx.AsyncClient:
        """Return the injected client or lazily create one for this source.

        A source is normally long-lived for the lifetime of the plugin.  Keep
        the fallback client alive as well so repeated CN requests can reuse
        its connection pool and keep-alive connections.  Injected clients
        remain owned by the caller and are never closed here.
        """

        if self._client is not None:
            return self._client
        if self._owned_client is None:
            self._owned_client = httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,
                proxy=self.proxy,
                trust_env=self.trust_env,
            )
        return self._owned_client

    async def aclose(self) -> None:
        """Close a client created by this data source, if any."""

        if self._owned_client is not None:
            await self._owned_client.aclose()
            self._owned_client = None

    @staticmethod
    def _normalize_season(season: Any) -> str:
        value = str(season).strip()
        if not value.isdigit() or int(value) < 1 or int(value) > 99:
            raise DataSourceError("赛季必须是 1 到 99 之间的数字")
        return str(int(value))

    def _body(self, uid: str = "", *, template: str | None = None, **extra: Any) -> dict[str, Any]:
        try:
            # Encode substituted values before parsing so user input cannot alter JSON.
            values = {"uid": uid, **extra}
            rendered = self.body_template if template is None else template
            for key, value in values.items():
                encoded = json.dumps(value, ensure_ascii=False)
                rendered = rendered.replace(f'"{{{key}}}"', encoded)
                rendered = rendered.replace(f"'{{{key}}}'", encoded)
                rendered = rendered.replace("{" + key + "}", encoded)
            body = json.loads(rendered)
        except json.JSONDecodeError as exc:
            raise DataSourceError("MRCN_REQUEST_BODY_TEMPLATE 无法生成有效 JSON") from exc
        if not isinstance(body, dict):
            raise DataSourceError("MRCN_REQUEST_BODY_TEMPLATE 必须是 JSON 对象")
        return body

    async def _post(self, path: str, uid: str, *, body_template: str | None = None, **extra: Any) -> dict[str, Any]:
        if not path:
            raise DataSourceError("该接口尚未配置，请设置对应的 MRCN_*_PATH")
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._request_client()
        try:
            template = body_template or self.body_template
            player_uid = int(uid) if uid.isdigit() else uid
            body = self._body_from(template, uid, player_uid=player_uid, **extra)
            if self.debug:
                print(f"[request] POST {path} body={json.dumps(body, ensure_ascii=False, separators=(',', ':'))}")
            response = await client.post(url, headers=self.headers, json=body)
            response.raise_for_status()
            payload = response.json()
            if self.debug:
                keys = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
                print(f"[response] HTTP {response.status_code} keys={keys}")
        except httpx.HTTPStatusError as exc:
            raise DataSourceError(f"国服接口返回 HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise DataSourceError(f"国服接口请求失败: {exc}") from exc
        if not isinstance(payload, dict):
            raise DataSourceError("国服接口返回格式不是 JSON 对象")
        self._raise_for_business_error(payload)
        return payload

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        if not path:
            return {"data": params}
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._request_client()
        try:
            if self.debug:
                print(f"[request] GET {path} params={json.dumps(params, ensure_ascii=False, separators=(',', ':'))}")
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            payload = response.json()
            if self.debug:
                keys = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
                print(f"[response] HTTP {response.status_code} keys={keys}")
        except httpx.HTTPStatusError as exc:
            raise DataSourceError(f"国服接口返回 HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise DataSourceError(f"国服接口请求失败: {exc}") from exc
        if not isinstance(payload, dict):
            raise DataSourceError("国服接口返回格式不是 JSON 对象")
        self._raise_for_business_error(payload)
        return payload

    def _body_from(self, template: str, uid: str, **extra: Any) -> dict[str, Any]:
        return self._body(uid, template=template, **extra)

    @staticmethod
    def _coerce_game_mode(game_mode: GameMode | int) -> GameMode:
        try:
            return GameMode(int(game_mode))
        except (TypeError, ValueError) as exc:
            raise DataSourceError("game_mode 只支持 QUICK(1) 或 COMPETITIVE(2)") from exc

    @staticmethod
    def _mode_suffix(game_mode: GameMode) -> str:
        return "quick" if game_mode is GameMode.QUICK else "competitive"

    def _mode_template(self, endpoint: str, game_mode: GameMode) -> str:
        """Resolve a mode template while retaining ranked-era config names."""

        generic = self.body_templates.get(endpoint, "")
        suffix = self._mode_suffix(game_mode)
        specific_name = f"{endpoint}_{suffix}"
        specific = self.body_templates.get(specific_name, "")
        if specific and specific != self.DEFAULT_BODY_TEMPLATES.get(specific_name):
            return specific
        legacy_name = f"{endpoint}_ranked"
        legacy = self.body_templates.get(legacy_name) if game_mode is GameMode.COMPETITIVE else None
        if legacy and legacy != self.DEFAULT_BODY_TEMPLATES.get(legacy_name):
            return legacy
        if "{game_mode_id}" in generic or "{play_mode_id}" in generic:
            return generic
        if specific:
            return specific
        return legacy or generic

    async def _load_mode(
        self,
        endpoint: str,
        uid: str,
        season: str,
        game_mode: GameMode | int,
        **extra: Any,
    ) -> dict[str, Any]:
        mode = self._coerce_game_mode(game_mode)
        cache_key = f"{endpoint}:{uid}:{season}:{self._mode_suffix(mode)}"
        if extra.get("hero_ids") is not None:
            cache_key += ":" + ",".join(str(item) for item in extra["hero_ids"])
        if self.mode_cache_seconds > 0:
            cached = self._mode_cache.get(cache_key)
            if cached and time.monotonic() - cached[0] < self.mode_cache_seconds:
                return cached[1]
            self._mode_cache.pop(cache_key, None)
        payload = await self._post(
            self.paths[endpoint],
            uid,
            body_template=self._mode_template(endpoint, mode),
            season=season,
            game_mode_id=int(mode),
            play_mode_id=DEFAULT_PLAY_MODE,
            **extra,
        )
        if self.mode_cache_seconds > 0:
            self._mode_cache[cache_key] = (time.monotonic(), payload)
        return payload

    async def load_career(
        self,
        uid: str,
        season: str | None,
        game_mode: GameMode | int,
    ) -> dict[str, Any]:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        return await self._load_mode(
            "career", uid, self._normalize_season(season or self.default_season), game_mode
        )

    async def load_sort_hero(
        self,
        uid: str,
        season: str | None,
        game_mode: GameMode | int,
    ) -> dict[str, Any]:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        return await self._load_mode(
            "sort_hero", uid, self._normalize_season(season or self.default_season), game_mode
        )

    async def load_hero_career(
        self,
        uid: str,
        hero_ids: list[int | str],
        season: str | None,
        game_mode: GameMode | int,
    ) -> dict[str, Any]:
        uid = str(uid).strip()
        if not uid.isdigit() or not hero_ids:
            raise DataSourceError("UID 必须是数字，hero_ids 不能为空")
        normalized_ids = [int(item) if str(item).isdigit() else str(item) for item in hero_ids]
        return await self._load_mode(
            "hero", uid, self._normalize_season(season or self.default_season), game_mode,
            hero_ids=normalized_ids,
        )

    @staticmethod
    def _response_uid(data: Mapping[str, Any]) -> str:
        return _text(data, "aid", "playerUid", "uid", "roleId")

    def _validate_response_uid(self, requested_uid: str, data: Mapping[str, Any]) -> str:
        response_uid = self._response_uid(data)
        if response_uid and response_uid != requested_uid:
            raise DataSourceError(
                f"请求目标与响应玩家不一致：请求 {requested_uid}，服务器返回 {response_uid}"
            )
        return response_uid or requested_uid

    async def _load_account_data(self, uid: str) -> tuple[dict[str, Any], dict[str, Any], str]:
        payload = await self._post(
            self.paths["data"], uid, body_template=self.body_templates["data"]
        )
        data = _first_mapping(payload.get("data", payload))
        response_uid = self._validate_response_uid(uid, data)
        return payload, data, response_uid

    async def validate_uid(self, uid: str) -> str:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        role = await self.resolve_role(uid)
        return self._validate_response_uid(uid, role)

    async def resolve_role(self, uid: str) -> dict[str, Any]:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        payload = await self._get(self.paths["role"], roleId=int(uid))
        role = _first_mapping(payload.get("data", payload))
        self._validate_response_uid(uid, role)
        return role

    @staticmethod
    def _business_error_message(payload: dict[str, Any], default: str = "业务请求失败") -> str:
        message = str(payload.get("message", payload.get("msg", payload.get("error", default))))
        if any(item in message for item in CNDataSource.PRIVATE_PROFILE_MESSAGES):
            return f"{message}\n{CNDataSource.PRIVATE_PROFILE_HINT}"
        return message

    @staticmethod
    def _raise_for_business_error(payload: dict[str, Any]) -> None:
        code = payload.get("code", payload.get("errCode", payload.get("errorCode")))
        if code not in (None, 0, "0", 200, "200"):
            message = CNDataSource._business_error_message(payload)
            raise DataSourceError(f"国服接口业务失败：{message}")
        if payload.get("success") is False or payload.get("error") is True:
            message = CNDataSource._business_error_message(payload)
            raise DataSourceError(f"国服接口业务失败：{message}")

    @staticmethod
    def _build_profile(
        data: Mapping[str, Any],
        role: Mapping[str, Any],
        response_uid: str,
        season: str,
    ) -> PlayerProfile:
        rank_scores = _rank_scores(data.get("rankGameSeason"))
        season_key = str(int(season))
        rank_score = rank_scores.get(season_key)
        if rank_score is None:
            score = _number(data, "rank_score", "rankScore", "currentRankScore")
            rank_score = int(round(score)) if score is not None else None
        return PlayerProfile(
            uid=response_uid,
            name=_text(data, "name", "playerName", "nickName", default=_text(role, "roleName", default="未知")),
            aid=response_uid,
            level=_number(data, "level"),
            club_team_name=_text(data, "clubTeamName", "clubName"),
            rank_game_season=_rank_text(data.get("rankGameSeason"), season) or _text(
                data, "rankSeason", "rankName"
            ),
            rank_level=_rank_level(data.get("rankGameSeason"), season) or _count(
                data, "rankLevel", "rankLevelId", "currentRankLevel"
            ),
            rank_history=_rank_levels(data.get("rankGameSeason")),
            rank_score=rank_score,
            rank_score_history=rank_scores,
        )

    @staticmethod
    def _combine_mode_stats(quick: ModeStats, competitive: ModeStats) -> ModeStats:
        def add(name: str):
            values = [getattr(quick, name), getattr(competitive, name)]
            present = [value for value in values if value is not None]
            return sum(present) if present else None

        def maximum(name: str):
            values = [getattr(quick, name), getattr(competitive, name)]
            present = [value for value in values if value is not None]
            return max(present) if present else None

        def merge_dynamic_sum() -> dict[str, float]:
            result: dict[str, float] = {}
            for source in (quick.dynamic_sum, competitive.dynamic_sum):
                for key, value in source.items():
                    result[key] = result.get(key, 0.0) + value
            return result

        def merge_dynamic_max() -> dict[str, float]:
            result: dict[str, float] = {}
            for source in (quick.dynamic_max, competitive.dynamic_max):
                for key, value in source.items():
                    result[key] = max(result.get(key, value), value)
            return result

        matches = add("matches")
        wins = add("wins")
        effective_matches = add("effective_matches")
        effective_wins = add("effective_wins")
        return ModeStats(
            matches=matches,
            effective_matches=effective_matches,
            wins=wins,
            effective_wins=effective_wins,
            kills=add("kills"),
            deaths=add("deaths"),
            assists=add("assists"),
            final_hits=add("final_hits"),
            solo_eliminations=add("solo_eliminations"),
            critical_eliminations=add("critical_eliminations"),
            main_attack_count=add("main_attack_count"),
            main_attack_hits=add("main_attack_hits"),
            max_kills=maximum("max_kills"),
            max_assists=maximum("max_assists"),
            max_final_hits=maximum("max_final_hits"),
            win_rate=(effective_wins * 100 / effective_matches)
            if effective_matches and effective_wins is not None
            else ((wins * 100 / matches) if matches and wins is not None else None),
            damage=add("damage"),
            hero_damage=add("hero_damage"),
            heal=add("heal"),
            damage_taken=add("damage_taken"),
            play_time_seconds=add("play_time_seconds"),
            mvp=add("mvp"),
            svp=add("svp"),
            dynamic_sum=merge_dynamic_sum(),
            dynamic_max=merge_dynamic_max(),
        )

    @staticmethod
    def _merge_mode_stats(existing: ModeStats, incoming: ModeStats) -> ModeStats:
        """Fill incomplete SortHero rows without discarding their play time."""

        values = {
            field_name: (
                getattr(incoming, field_name)
                if getattr(incoming, field_name) is not None
                else getattr(existing, field_name)
            )
            for field_name in ModeStats.__dataclass_fields__
        }
        for field_name in ("dynamic_sum", "dynamic_max"):
            values[field_name] = {
                **getattr(existing, field_name),
                **getattr(incoming, field_name),
            }
        return ModeStats(**values)

    async def get_player_profile(self, uid: str, season: str | None = None) -> PlayerProfile:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        season = self._normalize_season(season or self.default_season)
        role = await self.resolve_role(uid)
        response_uid = self._validate_response_uid(uid, role)
        _data_payload, data, response_uid = await self._load_account_data(response_uid)
        return self._build_profile(data, role, response_uid, season)

    async def get_player_profile_history(self, uid: str) -> PlayerProfile:
        """Load the lightweight profile whose rank map covers all CN seasons."""

        return await self.get_player_profile(uid)

    async def get_player(self, uid: str, season: str | None = None) -> PlayerStats:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        season = self._normalize_season(season or self.default_season)
        role = await self.resolve_role(uid)
        response_uid = self._validate_response_uid(uid, role)
        data_payload, data, response_uid = await self._load_account_data(response_uid)
        responses = {"role": role, "data": data_payload}

        career_quick, career_competitive, sort_quick, sort_competitive = await asyncio.gather(
            self.load_career(uid, season, GameMode.QUICK),
            self.load_career(uid, season, GameMode.COMPETITIVE),
            self.load_sort_hero(uid, season, GameMode.QUICK),
            self.load_sort_hero(uid, season, GameMode.COMPETITIVE),
        )
        responses["career_quick"] = career_quick
        responses["career_competitive"] = career_competitive
        quick_stats = _mode_stats(career_quick.get("data", career_quick))
        competitive_stats = _mode_stats(career_competitive.get("data", career_competitive))
        for payload in (career_quick, career_competitive):
            returned_uid = self._response_uid(_career_mapping(payload.get("data", payload)))
            if returned_uid and returned_uid != response_uid:
                raise DataSourceError("国服接口返回了不一致的账号 UID，已拒绝展示数据")

        profile = self._build_profile(data, role, response_uid, season)
        total = self._combine_mode_stats(quick_stats, competitive_stats)
        career_summary = CareerSummary(
            matches=total.matches,
            wins=total.wins,
            kills=total.kills,
            deaths=total.deaths,
            assists=total.assists,
            win_rate=total.win_rate,
            damage=total.damage,
            hero_damage=total.hero_damage,
            quick=quick_stats,
            competitive=competitive_stats,
        )

        responses["sort_hero_quick"] = sort_quick
        responses["sort_hero_competitive"] = sort_competitive
        heroes = self._merge_heroes(
            self._parse_heroes(sort_quick, "quick_discovery"),
            self._parse_heroes(sort_competitive, "competitive_discovery"),
        )
        heroes = await self._enrich_sort_hero_candidates(uid, season, heroes)
        return PlayerStats(profile=profile, summary=career_summary, heroes=heroes, season=season, raw=responses)

    async def _load_hero_mode_batch(
        self,
        uid: str,
        hero_ids: list[int],
        season: str,
        game_mode: GameMode,
        fallback_semaphore: asyncio.Semaphore | None = None,
    ) -> dict[str, ModeStats]:
        """Load all selected heroes for one mode with one batch request."""

        try:
            payload = await self.load_hero_career(uid, hero_ids, season, game_mode)
            parsed = self.parse_hero_career(payload, hero_ids, game_mode)
        except DataSourceError as exc:
            logger.warning(
                "CN HeroCareer batch failed season=%s mode=%s heroes=%s error=%s",
                season,
                self._mode_suffix(game_mode),
                len(hero_ids),
                exc,
            )
            # Preserve the old per-hero degradation path when the observed
            # batch endpoint rejects a request.  This is an error-only
            # fallback; successful batch responses still use one request per
            # mode and missing rows remain missing rather than being guessed.
            semaphore = fallback_semaphore if fallback_semaphore is not None else asyncio.Semaphore(4)
            results = await asyncio.gather(*(
                self._load_one_hero_mode(uid, str(hero_id), season, game_mode, semaphore)
                for hero_id in hero_ids
            ))
            return {
                str(hero_id): stats
                for hero_id, stats in zip(hero_ids, results)
                if stats is not None
            }
        return {hero.hero_id: hero.total for hero in parsed}

    async def _load_one_hero_mode(
        self,
        uid: str,
        hero_id: str,
        season: str,
        game_mode: GameMode,
        semaphore: asyncio.Semaphore,
    ) -> ModeStats | None:
        """Load one authoritative HeroCareer row without failing its siblings."""

        async with semaphore:
            try:
                payload = await self.load_hero_career(
                    uid,
                    [int(hero_id)],
                    season,
                    game_mode,
                )
            except DataSourceError as exc:
                logger.warning(
                    "CN HeroCareer failed hero=%s season=%s mode=%s error=%s",
                    hero_id,
                    season,
                    self._mode_suffix(game_mode),
                    exc,
                )
                return None

        row = next(
            (
                item for item in self._hero_items(payload)
                if _text(item, "heroId", "id") == str(hero_id)
            ),
            None,
        )
        if row is None:
            logger.warning(
                "CN HeroCareer returned no row hero=%s season=%s mode=%s",
                hero_id,
                season,
                self._mode_suffix(game_mode),
            )
            return None
        return _mode_stats(row)

    async def _enrich_sort_hero_candidates(
        self,
        uid: str,
        season: str,
        heroes: list[PlayerHeroStats],
    ) -> list[PlayerHeroStats]:
        """Treat SortHero as discovery and HeroCareer as the stats authority.

        ``loadSortHero`` is observed to return useful hero IDs and play-time
        ordering, but its match/win fields are not reliable across seasons.
        Therefore every displayed candidate is queried independently for each
        explicit mode.  A failed hero/mode keeps ``None`` while a successful
        response containing zero keeps ``0``.
        """

        if not heroes:
            return heroes
        selected = [
            hero for hero in heroes[:10]
            if str(hero.hero_id).isdigit()
        ]
        if not selected:
            return heroes

        hero_ids = [int(hero.hero_id) for hero in selected]
        fallback_semaphore = asyncio.Semaphore(4)
        quick_stats, competitive_stats = await asyncio.gather(
            self._load_hero_mode_batch(
                uid, hero_ids, season, GameMode.QUICK, fallback_semaphore
            ),
            self._load_hero_mode_batch(
                uid, hero_ids, season, GameMode.COMPETITIVE, fallback_semaphore
            ),
        )
        for hero in selected:
            quick = quick_stats.get(str(hero.hero_id))
            competitive = competitive_stats.get(str(hero.hero_id))
            if quick is not None:
                hero.quick = self._merge_mode_stats(hero.quick, quick)
            if competitive is not None:
                hero.competitive = self._merge_mode_stats(hero.competitive, competitive)
                hero.ranked = hero.competitive
            self._refresh_hero_total(hero)

        enriched = sorted(
            selected,
            key=lambda item: (
                item.total_matches is not None,
                item.total_matches if item.total_matches is not None else -1,
            ),
            reverse=True,
        )
        selected_ids = {str(hero.hero_id) for hero in selected}
        return enriched + [hero for hero in heroes if str(hero.hero_id) not in selected_ids]

    async def get_summary_detail(self, uid: str) -> dict[str, Any]:
        match_uid = str(uid).strip()
        match_uid = re.sub(r"^matchuid\s*[:=：]\s*", "", match_uid, flags=re.IGNORECASE)
        if not match_uid:
            raise DataSourceError("matchUid 不能为空")
        return await self.get_summary_details([match_uid])

    async def get_summary_details(self, match_uids: list[str]) -> dict[str, Any]:
        normalized = [str(item).strip() for item in match_uids if str(item).strip()]
        if not normalized:
            raise DataSourceError("matchUid 不能为空")
        return await self._post(
            self.paths["summary_detail"], "",
            body_template=self.body_templates["summary_detail"],
            match_uids=normalized,
        )

    async def get_hero(self, uid: str, hero_id: str, season: str | None = None) -> dict[str, Any]:
        uid, hero_id = str(uid).strip(), str(hero_id).strip()
        if not uid.isdigit() or not hero_id:
            raise DataSourceError("UID must be numeric and hero_id cannot be empty")
        season = self._normalize_season(season or self.default_season)
        await self.validate_uid(uid)
        # The old unscoped method is retained for CLI compatibility.  New
        # callers should use load_hero_career with an explicit mode.
        return await self.load_hero_career(
            uid,
            [int(hero_id)] if hero_id.isdigit() else [hero_id],
            season,
            GameMode.COMPETITIVE,
        )

    async def get_hero_profile(self, uid: str, hero_id: str, season: str | None = None) -> PlayerHeroStats:
        """Load one hero from the two explicit CN mode scopes."""

        uid, hero_id = str(uid).strip(), str(hero_id).strip()
        if not uid.isdigit() or not hero_id:
            raise DataSourceError("UID must be numeric and hero_id cannot be empty")
        season = self._normalize_season(season or self.default_season)
        await self.validate_uid(uid)
        hero_ids = [int(hero_id)] if hero_id.isdigit() else [hero_id]
        quick, competitive = await asyncio.gather(
            self.load_hero_career(uid, hero_ids, season, GameMode.QUICK),
            self.load_hero_career(uid, hero_ids, season, GameMode.COMPETITIVE),
        )
        hero = PlayerHeroStats(hero_id=hero_id, hero_name=get_hero_name(hero_id))
        self._enrich_heroes([hero], quick, "quick")
        self._enrich_heroes([hero], competitive, "competitive")
        self._refresh_hero_total(hero)
        return hero

    @staticmethod
    def _hero_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        value = payload.get("data", payload)
        if isinstance(value, list):
            items = value
        elif isinstance(value, dict):
            items = value.get(
                "careers",
                value.get("heros", value.get("heroes", value.get("heroList", []))),
            )
        else:
            items = []
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    def _parse_heroes(self, payload: dict[str, Any], scope: str = "total") -> list[PlayerHeroStats]:
        result: list[PlayerHeroStats] = []
        for item in self._hero_items(payload):
            hero_id = _text(item, "heroId", "id")
            if not hero_id:
                continue
            stats = _mode_stats(item)
            if scope.endswith("_discovery"):
                # SortHero contributes identity/order and, where available,
                # mode play time only.  Its match/win values are deliberately
                # ignored because HeroCareer is the authoritative source.
                stats = ModeStats(play_time_seconds=stats.play_time_seconds)
            hero = PlayerHeroStats(
                hero_id=hero_id,
                hero_name=get_hero_name(hero_id, _text(item, "heroName", "name") or None),
                raw=dict(item),
            )
            if scope in {"quick", "quick_discovery"}:
                hero.quick = stats
            elif scope in {"competitive", "competitive_discovery"}:
                hero.competitive = stats
                hero.ranked = hero.competitive
            elif scope == "total":
                hero.total = stats
            else:
                raise ValueError(f"unknown hero scope: {scope}")
            self._refresh_hero_total(hero)
            result.append(hero)
        return result

    def parse_hero_career(
        self,
        payload: dict[str, Any],
        hero_ids: list[int | str],
        game_mode: GameMode | int,
    ) -> list[PlayerHeroStats]:
        """Parse a batched HeroCareer response using the existing CN parser."""

        mode = self._coerce_game_mode(game_mode)
        requested = {str(item) for item in hero_ids}
        scope = "quick" if mode is GameMode.QUICK else "competitive"
        return [
            hero
            for hero in self._parse_heroes(payload, scope)
            if hero.hero_id in requested
        ]

    @classmethod
    def _merge_heroes(cls, *groups: list[PlayerHeroStats]) -> list[PlayerHeroStats]:
        merged: dict[str, PlayerHeroStats] = {}
        for group in groups:
            for hero in group:
                current = merged.get(hero.hero_id)
                if current is None:
                    current = PlayerHeroStats(
                        hero_id=hero.hero_id,
                        hero_name=hero.hero_name,
                        quick=hero.quick,
                        competitive=hero.competitive,
                        raw=dict(hero.raw),
                    )
                    merged[hero.hero_id] = current
                else:
                    if hero.hero_name and current.hero_name == "未知英雄":
                        current.hero_name = hero.hero_name
                    if not _mode_stats_is_empty(hero.quick):
                        current.quick = cls._merge_mode_stats(current.quick, hero.quick)
                    if not _mode_stats_is_empty(hero.competitive):
                        current.competitive = cls._merge_mode_stats(current.competitive, hero.competitive)
                    current.raw = {**current.raw, **hero.raw}
                cls._refresh_hero_total(current)
        return list(merged.values())

    @staticmethod
    def _refresh_hero_total(hero: PlayerHeroStats) -> None:
        total = CNDataSource._combine_mode_stats(hero.quick, hero.competitive)
        if total.matches is None and not _mode_stats_is_empty(hero.total):
            total = hero.total
        hero.total = total
        hero.total_matches = total.matches
        hero.total_wins = total.wins
        hero.total_win_rate = total.win_rate
        hero.total_play_time_seconds = total.play_time_seconds
        hero.ranked = hero.competitive

    def _enrich_heroes(
        self,
        heroes: list[PlayerHeroStats],
        payload: dict[str, Any],
        scope: str,
    ) -> list[PlayerHeroStats]:
        details = {
            _text(item, "heroId", "id"): item
            for item in self._hero_items(payload)
            if _text(item, "heroId", "id")
        }
        for hero in heroes:
            item = details.get(hero.hero_id)
            if not item:
                continue
            stats = _mode_stats(item)
            if _mode_stats_is_empty(stats):
                continue
            if scope == "quick":
                hero.quick = self._merge_mode_stats(hero.quick, stats)
            elif scope == "competitive":
                hero.competitive = self._merge_mode_stats(hero.competitive, stats)
                hero.ranked = hero.competitive
            elif scope == "total":
                hero.total = stats
            else:
                raise ValueError(f"unknown hero scope: {scope}")
            hero.hero_name = get_hero_name(
                hero.hero_id, _text(item, "heroName", "name") or hero.hero_name
            )
            hero.raw = {**hero.raw, **item}
        return heroes

    async def get_recent_payload(self, uid: str, season: str | None = None) -> dict[str, Any]:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID must be numeric")
        season = self._normalize_season(season or self.default_season)
        await self.validate_uid(uid)
        return await self._post(
            self.paths["matches"], uid, body_template=self.body_templates["matches"], season=season
        )

    @staticmethod
    def _summary_items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        value: Any = payload.get("data", payload)
        if isinstance(value, Mapping):
            value = value.get(
                "matchInfo",
                value.get("matches", value.get("matchList", value.get("records", value.get("list", [])))),
            )
        return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []

    async def get_match_summary_page(
        self,
        uid: str,
        season: str | None = None,
        *,
        page: int = 0,
        page_size: int = 100,
        start_timestamp: int | None = None,
        end_timestamp: int | None = None,
        game_mode_ids: tuple[int, ...] = (1, 2, 4),
        play_mode_ids: tuple[int, ...] = (0, 7, 8),
    ) -> MatchSummaryPage:
        """Load one Summary page with optional server-side time bounds."""

        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError) as exc:
            raise DataSourceError("page 和 page_size 必须是整数") from exc
        if page < 0 or page_size <= 0:
            raise DataSourceError("page 必须不小于 0，page_size 必须是正整数")
        if (start_timestamp is None) != (end_timestamp is None):
            raise DataSourceError("时间范围必须同时提供开始和结束时间")
        if start_timestamp is not None and end_timestamp is not None and end_timestamp <= start_timestamp:
            raise DataSourceError("时间范围结束时间必须晚于开始时间")
        normalized_season = self._normalize_season(season or self.default_season) if season else None
        template = self.body_templates["matches"]
        body = self._body_from(
            template,
            uid,
            season=normalized_season or "",
            player_uid=int(uid),
            page=page,
            page_size=page_size,
            game_mode_ids=list(game_mode_ids),
            play_mode_ids=list(play_mode_ids),
        )
        # Keep the legacy JSON template stable while making pagination and
        # optional range conditions code-owned fields.
        body["page"] = page
        body["pageSize"] = page_size
        body["playerUid"] = int(uid)
        body["gameModeId"] = {"$in": [int(item) for item in game_mode_ids]}
        body["playModeId"] = {"$in": [int(item) for item in play_mode_ids]}
        body.pop("matchTimeStamp", None)
        if season is None:
            # Time-window queries are intentionally season-independent.  The
            # default legacy template contains matchSeason, so remove that
            # condition after expansion instead of changing user templates.
            body.pop("matchSeason", None)
        if start_timestamp is not None and end_timestamp is not None:
            body["matchTimeStamp"] = {
                "$gte": int(start_timestamp),
                "$lt": int(end_timestamp),
            }
        payload = await self._post(
            self.paths["matches"],
            uid,
            body_template=json.dumps(body, ensure_ascii=False),
            season=normalized_season or self.default_season,
        )
        return MatchSummaryPage(
            match_info=self._summary_items(payload),
            page=page,
            page_size=page_size,
            raw=payload,
        )

    async def get_recent_matches(self, uid: str, season: str | None = None) -> list[dict]:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        season_code = self._normalize_season(season or self.default_season)
        page = await self.get_match_summary_page(uid, season_code, page=0, page_size=10)
        matches = page.match_info
        match_uids = [_text(item, "matchUid", "matchUID") for item in matches]
        match_uids = [item for item in match_uids if item]
        if not match_uids:
            return matches
        details_payload = await self.get_summary_details(match_uids)
        details_data = details_payload.get("data", details_payload)
        details = details_data.get("matches", []) if isinstance(details_data, dict) else []
        detail_by_uid = {
            _text(item, "matchUid", "matchUID"): item
            for item in details
            if isinstance(item, dict)
        }
        for match in matches:
            detail = detail_by_uid.get(_text(match, "matchUid", "matchUID"))
            players = detail.get("matchPlayers", []) if isinstance(detail, dict) else []
            target = next(
                (
                    player for player in players
                    if isinstance(player, dict) and _text(player, "playerUid", "uid") == uid
                ),
                None,
            )
            if isinstance(target, dict):
                player = match.setdefault("matchPlayer", {})
                if isinstance(player, dict):
                    match["matchPlayer"] = dict(target)
        return matches

    @staticmethod
    def normalize_match(item: dict[str, Any]) -> RecentMatch | None:
        match_uid = _text(item, "matchUid", "matchUID", "matchUids", "uid", "id")
        if not match_uid:
            return None
        return RecentMatch(
            match_uid=match_uid,
            result=_text(item, "result", "resultName", "win", "isWin", default="?"),
            hero_name=_text(item, "heroName", "hero", "hero_name", default="未知英雄"),
            kills=_number(item, "kills", "k", "kill") or "-",
            deaths=_number(item, "deaths", "d", "death") or "-",
            assists=_number(item, "assists", "a", "assist") or "-",
            raw=item,
        )
