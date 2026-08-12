from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

import httpx

from ..models import CareerSummary, HeroStat, PlayerProfile, PlayerStats, RecentMatch
from .base import DataSourceError, RivalsDataSource


def _number(data: Mapping[str, Any], *keys: str) -> int | float | None:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            try:
                return float(value) if isinstance(value, str) and "." in value else int(value)
            except (TypeError, ValueError):
                continue
    return None


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


class CNDataSource(RivalsDataSource):
    """Adapter for the CN mini-program API observed in mitmproxy.

    The capture established endpoint names, but not a stable public contract.
    Request body and headers are therefore configurable rather than guessed in
    the plugin. This also keeps short-lived credentials out of source control.
    """

    DEFAULT_PATHS = {
        "data": "/api/game/player/loadData",
        "summary": "/api/game/player/loadSummary",
        "summary_detail": "/api/game/player/loadSummaryDetail",
        "career": "/api/game/player/loadCareer",
        "hero": "/api/game/player/loadHeroCareer",
        "sort_hero": "/api/game/player/loadSortHero",
        "matches": "/api/game/player/loadSummary",
    }

    DEFAULT_BODY_TEMPLATES = {
        "data": "{}",
        "summary": '{"matchSeason":{"$eq":"19"},"gameModeId":{"$in":[1,2,4]},"playModeId":{"$in":[0,7,8]},"page":0,"pageSize":3}',
        "summary_detail": '{"matchUids":["{match_uid}"]}',
        "career": '{"matchSeason":"19"}',
        "hero": '{"heroIdList":{hero_ids},"matchSeason":"19"}',
        "sort_hero": '{"matchSeason":"19"}',
        "matches": '{"matchSeason":{"$eq":"19"},"gameModeId":{"$in":[1,2,4]},"playModeId":{"$in":[0,7,8]},"page":0,"pageSize":10}',
    }

    def __init__(self, *, client: httpx.AsyncClient | None = None, env: Mapping[str, Any] | None = None):
        config = os.environ if env is None else env
        base_url = config.get("MRCN_API_BASE_URL", "").strip().rstrip("/")
        if not base_url:
            raise DataSourceError("未配置 MRCN_API_BASE_URL，请先填写官方小程序接口前缀")
        self.base_url = base_url
        self.timeout = float(config.get("MRCN_TIMEOUT_SECONDS", "10"))
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
        self._client = client

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
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        try:
            template = body_template or self.body_template
            response = await client.post(url, headers=self.headers, json=self._body_from(template, uid, **extra))
            response.raise_for_status()
            payload = response.json()
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
    def _raise_for_business_error(payload: dict[str, Any]) -> None:
        code = payload.get("code", payload.get("errCode", payload.get("errorCode")))
        if code not in (None, 0, "0", 200, "200"):
            message = payload.get("message", payload.get("msg", payload.get("error", "业务请求失败")))
            raise DataSourceError(f"国服接口业务失败：{message}")
        if payload.get("success") is False or payload.get("error") is True:
            message = payload.get("message", payload.get("msg", "业务请求失败"))
            raise DataSourceError(f"国服接口业务失败：{message}")

    async def get_player(self, uid: str) -> PlayerStats:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        responses = {}
        for name in ("data", "summary", "career", "sort_hero"):
            responses[name] = await self._post(self.paths[name], uid, body_template=self.body_templates[name])
        data = _first_mapping(responses["data"].get("data", responses["data"]))
        summary = _first_mapping(responses["summary"].get("data", responses["summary"]))
        career = _first_mapping(responses["career"].get("data", responses["career"]))
        profile = PlayerProfile(
            uid=uid,
            name=_text(data, "name", "playerName", "nickName", default="未知"),
            aid=_text(data, "aid", "playerUid", "uid"),
            level=_number(data, "level"),
            club_team_name=_text(data, "clubTeamName", "clubName"),
            rank_game_season=_text(data, "rankGameSeason", "rankSeason", "rankName"),
        )
        # loadData contains the account aggregate in the observed response;
        # loadSummary is the paginated match list, not the aggregate.
        source = {**data, **summary, **career}
        matches = _number(source, "totalMatchCount", "matchCount", "totalMatches")
        wins = _number(source, "totalMatchWinCount", "winCount", "wins")
        win_rate = _number(source, "winRate")
        if win_rate is None and matches:
            win_rate = wins * 100 / matches if wins is not None else None
        career_summary = CareerSummary(
            matches=matches,
            wins=wins,
            kills=_number(source, "k", "kills", "totalKill"),
            deaths=_number(source, "d", "deaths", "totalDeath"),
            assists=_number(source, "a", "assists", "totalAssist"),
            win_rate=win_rate,
            damage=_number(source, "totalDamage", "damage"),
            hero_damage=_number(source, "totalHeroDamage", "heroDamage"),
        )
        heroes = self._parse_heroes(responses["sort_hero"])
        return PlayerStats(profile, career_summary, heroes, responses)

    async def get_summary_detail(self, uid: str) -> dict[str, Any]:
        match_uid = str(uid).strip()
        if not match_uid:
            raise DataSourceError("match_uid cannot be empty")
        return await self._post(
            self.paths["summary_detail"], "",
            body_template=self.body_templates["summary_detail"],
            match_uid=match_uid,
        )

    async def get_hero(self, uid: str, hero_id: str) -> dict[str, Any]:
        uid, hero_id = str(uid).strip(), str(hero_id).strip()
        if not uid.isdigit() or not hero_id:
            raise DataSourceError("UID must be numeric and hero_id cannot be empty")
        return await self._post(
            self.paths["hero"], uid,
            body_template=self.body_templates["hero"],
            hero_ids=[int(hero_id)] if hero_id.isdigit() else [hero_id],
        )

    def _parse_heroes(self, payload: dict[str, Any]) -> list[HeroStat]:
        value = payload.get("data", payload)
        items = value if isinstance(value, list) else value.get("heroes", value.get("heroList", [])) if isinstance(value, dict) else []
        if not isinstance(items, list):
            return []
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            matches = _number(item, "totalMatchCount", "matchCount", "matches")
            wins = _number(item, "totalMatchWinCount", "winCount", "wins")
            rate = _number(item, "winRate")
            if rate is None and matches and wins is not None:
                rate = wins * 100 / matches
            result.append(HeroStat(_text(item, "heroId", "id"), _text(item, "heroName", "name", default="未知英雄"), matches, rate, item))
        return result

    async def get_recent_matches(self, uid: str) -> list[dict]:
        uid = str(uid).strip()
        if not uid.isdigit():
            raise DataSourceError("UID 必须是数字")
        payload = await self._post(self.paths["matches"], uid, body_template=self.body_templates["matches"])
        value = payload.get("data", payload)
        if isinstance(value, dict):
            value = value.get("matches", value.get("matchList", value.get("records", value.get("list", []))))
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

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
