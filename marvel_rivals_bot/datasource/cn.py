from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Mapping
from typing import Any

import httpx

from ..reference.heroes import get_hero_name
from ..reference.ranks import CN_RANK_LEVEL_MAP
from ..models import CareerSummary, ModeStats, PlayerHeroStats, PlayerProfile, PlayerStats, RecentMatch
from .base import DEFAULT_PLAY_MODE, DataSourceError, GameMode, RivalsDataSource


# Compatibility name: CN's detailed API levels remain distinct from Meta's
# broad rank buckets.
RANK_LEVEL_MAP = CN_RANK_LEVEL_MAP


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
    matches = _number(data, "totalMatchCount", "matchCount", "matches", "totalMatches")
    wins = _number(data, "totalMatchWinCount", "totalWinCount", "winCount", "wins")
    win_rate = _number(data, "winRate")
    if win_rate is None and matches and wins is not None:
        win_rate = wins * 100 / matches
    return ModeStats(
        matches=round(matches) if matches is not None else None,
        wins=round(wins) if wins is not None else None,
        kills=_count(data, "k", "kills", "totalKill"),
        deaths=_count(data, "d", "deaths", "totalDeath"),
        assists=_count(data, "a", "assists", "totalAssist"),
        win_rate=win_rate,
        damage=_count(data, "totalDamage", "damage"),
        hero_damage=_count(data, "totalHeroDamage", "heroDamage"),
        heal=_count(data, "totalHeroHeal", "totalHeal", "heroHeal", "heal"),
        damage_taken=_count(data, "totalDamageTaken", "damageTaken"),
        hit_rate=_number(data, "sessionMaxHitRate", "hitRate"),
        play_time_seconds=_number(data, "totalPlayTime", "playTime"),
        mvp=_count(data, "totalMvpTimes", "mvp", "mvpTimes"),
        svp=_count(data, "totalSvpTimes", "svp", "svpTimes"),
    )


def _mode_stats_is_empty(value: ModeStats) -> bool:
    return all(getattr(value, field_name) is None for field_name in ModeStats.__dataclass_fields__)


def _rank_level(value: Any, season: str = "19") -> int | None:
    if not isinstance(value, (str, Mapping)) or not value:
        return None
    try:
        seasons = json.loads(value) if isinstance(value, str) else value
        current = seasons.get(f"10010{int(season):02d}") if isinstance(seasons, dict) else None
        rank = json.loads(current) if isinstance(current, str) else current
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(rank, dict):
        return None
    level = _number(rank, "level")
    return int(level) if level is not None else None


def _rank_text(value: Any, season: str = "19") -> str:
    if not isinstance(value, (str, Mapping)) or not value:
        return ""
    try:
        seasons = json.loads(value) if isinstance(value, str) else value
        current = seasons.get(f"10010{int(season):02d}") if isinstance(seasons, dict) else None
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

    @staticmethod
    def _normalize_season(season: Any) -> str:
        value = str(season).strip()
        if not value.isdigit() or int(value) < 1 or int(value) > 99:
            raise DataSourceError("赛季必须是 1 到 99 之间的数字")
        return str(int(value))

    def _body(self, uid: str = "", **extra: Any) -> dict[str, Any]:
        try:
            # Encode substituted values before parsing so user input cannot alter JSON.
            values = {"uid": uid, **extra}
            rendered = self.body_template
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
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.timeout,
            verify=self.verify_ssl,
            proxy=self.proxy,
            trust_env=self.trust_env,
        )
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
        finally:
            if own_client:
                await client.aclose()
        if not isinstance(payload, dict):
            raise DataSourceError("国服接口返回格式不是 JSON 对象")
        self._raise_for_business_error(payload)
        return payload

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        if not path:
            return {"data": params}
        url = f"{self.base_url}/{path.lstrip('/')}"
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.timeout,
            verify=self.verify_ssl,
            proxy=self.proxy,
            trust_env=self.trust_env,
        )
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
        finally:
            if own_client:
                await client.aclose()
        if not isinstance(payload, dict):
            raise DataSourceError("国服接口返回格式不是 JSON 对象")
        self._raise_for_business_error(payload)
        return payload

    def _body_from(self, template: str, uid: str, **extra: Any) -> dict[str, Any]:
        old_template = self.body_template
        self.body_template = template
        try:
            return self._body(uid, **extra)
        finally:
            self.body_template = old_template

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
        )

    @staticmethod
    def _combine_mode_stats(quick: ModeStats, competitive: ModeStats) -> ModeStats:
        def add(name: str):
            values = [getattr(quick, name), getattr(competitive, name)]
            present = [value for value in values if value is not None]
            return sum(present) if present else None

        matches = add("matches")
        wins = add("wins")
        return ModeStats(
            matches=matches,
            wins=wins,
            kills=add("kills"),
            deaths=add("deaths"),
            assists=add("assists"),
            win_rate=(wins * 100 / matches) if matches and wins is not None else None,
            damage=add("damage"),
            hero_damage=add("hero_damage"),
            heal=add("heal"),
            damage_taken=add("damage_taken"),
            play_time_seconds=add("play_time_seconds"),
            mvp=add("mvp"),
            svp=add("svp"),
        )

    async def get_player_profile(self, uid: str, season: str | None = None) -> PlayerProfile:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        season = self._normalize_season(season or self.default_season)
        role = await self.resolve_role(uid)
        response_uid = self._validate_response_uid(uid, role)
        _data_payload, data, response_uid = await self._load_account_data(response_uid)
        return self._build_profile(data, role, response_uid, season)

    async def get_player(self, uid: str, season: str | None = None) -> PlayerStats:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        season = self._normalize_season(season or self.default_season)
        role = await self.resolve_role(uid)
        response_uid = self._validate_response_uid(uid, role)
        data_payload, data, response_uid = await self._load_account_data(response_uid)
        responses = {"role": role, "data": data_payload}

        career_quick = await self.load_career(uid, season, GameMode.QUICK)
        career_competitive = await self.load_career(uid, season, GameMode.COMPETITIVE)
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

        sort_quick = await self.load_sort_hero(uid, season, GameMode.QUICK)
        sort_competitive = await self.load_sort_hero(uid, season, GameMode.COMPETITIVE)
        responses["sort_hero_quick"] = sort_quick
        responses["sort_hero_competitive"] = sort_competitive
        heroes = self._merge_heroes(
            self._parse_heroes(sort_quick, "quick"),
            self._parse_heroes(sort_competitive, "competitive"),
        )
        return PlayerStats(profile=profile, summary=career_summary, heroes=heroes, season=season, raw=responses)

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
        quick = await self.load_hero_career(uid, hero_ids, season, GameMode.QUICK)
        competitive = await self.load_hero_career(uid, hero_ids, season, GameMode.COMPETITIVE)
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
            hero = PlayerHeroStats(
                hero_id=hero_id,
                hero_name=get_hero_name(hero_id, _text(item, "heroName", "name") or None),
                raw=dict(item),
            )
            if scope == "quick":
                hero.quick = stats
            elif scope == "competitive":
                hero.competitive = stats
                hero.ranked = hero.competitive
            elif scope == "total":
                hero.total = stats
            else:
                raise ValueError(f"unknown hero scope: {scope}")
            self._refresh_hero_total(hero)
            result.append(hero)
        return result

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
                    if hero.quick.matches is not None:
                        current.quick = hero.quick
                    if hero.competitive.matches is not None:
                        current.competitive = hero.competitive
                    current.raw = {**current.raw, **hero.raw}
                cls._refresh_hero_total(current)
        return sorted(
            merged.values(),
            key=lambda item: (item.total_matches or 0, str(item.hero_id)),
            reverse=True,
        )

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
                hero.quick = stats
            elif scope == "competitive":
                hero.competitive = stats
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

    async def get_recent_matches(self, uid: str, season: str | None = None) -> list[dict]:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        payload = await self.get_recent_payload(uid, season)
        value = payload.get("data", payload)
        if isinstance(value, dict):
            value = value.get("matchInfo", value.get("matches", value.get("matchList", value.get("records", value.get("list", [])))))
        matches = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
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
                    player["curHeroId"] = target.get("curHeroId")
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
