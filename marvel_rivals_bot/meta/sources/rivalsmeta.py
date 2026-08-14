"""HTTP adapter and schema validator for the RivalsMeta hero stats API."""

from __future__ import annotations

import copy
import asyncio
import math
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import httpx

from ..errors import MetaDataSourceError, MetaHTTPError, MetaSchemaError
from ..models import (
    RawBanRankBucket,
    RawBanStat,
    RawHeroMetaPayload,
    RawHeroMetaStat,
    RawHeroRankBucket,
)
from ..ranks import RANK_LABELS
from .base import MetaDataSource


DEFAULT_BASE_URL = "https://rivalsmeta.com"
HERO_STATS_PATH = "/api/heroes/stats"


class RivalsMetaSource(MetaDataSource):
    """Fetch and validate one complete RivalsMeta season payload.

    A client can be injected for tests or for a host application's transport
    policy. When no client is injected, requests use the bounded, environment-
    independent client required by the Meta provider contract.
    """

    DEFAULT_BASE_URL = DEFAULT_BASE_URL
    DEFAULT_HERO_STATS_PATH = HERO_STATS_PATH
    SOURCE_NAME = "RivalsMeta"
    RETRY_STATUSES = frozenset({502, 503, 504})

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        env: Mapping[str, Any] | None = None,
        base_url: str | None = None,
        path: str | None = None,
        timeout: float | None = None,
    ) -> None:
        config = os.environ if env is None else env
        configured_base = base_url or config.get("MRCN_RIVALSMETA_BASE_URL", self.DEFAULT_BASE_URL)
        configured_path = path or config.get(
            "MRCN_RIVALSMETA_HERO_STATS_PATH",
            config.get("MRCN_RIVALSMETA_PATH", self.DEFAULT_HERO_STATS_PATH),
        )
        self.base_url = str(configured_base).strip().rstrip("/")
        self.path = "/" + str(configured_path).strip().lstrip("/")
        if not self.base_url:
            raise MetaDataSourceError("RivalsMeta base URL 不能为空")
        try:
            self.timeout = float(timeout if timeout is not None else config.get("MRCN_META_TIMEOUT_SECONDS", "10"))
        except (TypeError, ValueError) as exc:
            raise MetaDataSourceError("MRCN_META_TIMEOUT_SECONDS 不是有效数字") from exc
        if self.timeout <= 0:
            raise MetaDataSourceError("MRCN_META_TIMEOUT_SECONDS 必须大于 0")
        self._client = client

    @property
    def url(self) -> str:
        return f"{self.base_url}{self.path}"

    async def get_hero_stats(self, season: str) -> RawHeroMetaPayload:
        season_value = str(season).strip()
        if not season_value or not season_value.isdigit():
            raise MetaDataSourceError("Meta season 不能为空")
        if self._client is not None:
            return await self._get_with_client(self._client, season_value)
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            trust_env=False,
        ) as client:
            return await self._get_with_client(client, season_value)

    async def _get_with_client(self, client: httpx.AsyncClient, season: str) -> RawHeroMetaPayload:
        for attempt in range(2):
            try:
                response = await client.get(self.url, params={"season": season})
            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                if attempt == 0:
                    await asyncio.sleep(0.3)
                    continue
                raise MetaDataSourceError(f"RivalsMeta 请求失败：{type(exc).__name__}") from exc
            except httpx.HTTPError as exc:
                raise MetaDataSourceError(f"RivalsMeta 请求失败：{type(exc).__name__}") from exc

            if response.status_code in self.RETRY_STATUSES and attempt == 0:
                await asyncio.sleep(0.3)
                continue
            if response.is_error:
                raise MetaHTTPError(response.status_code, f"RivalsMeta 返回 HTTP {response.status_code}")
            try:
                payload = response.json()
            except ValueError as exc:
                raise MetaSchemaError("RivalsMeta 响应不是有效 JSON") from exc
            parsed = self.parse_payload(payload)
            if parsed.season != int(season):
                raise MetaSchemaError(
                    f"RivalsMeta 响应赛季 {parsed.season} 与请求赛季 {season} 不一致"
                )
            return parsed
        raise MetaDataSourceError("RivalsMeta 请求失败")

    def parse_payload(self, payload: Any) -> RawHeroMetaPayload:
        if not isinstance(payload, dict):
            raise MetaSchemaError("Meta payload 顶层必须是对象")
        if "season" not in payload:
            raise MetaSchemaError("Meta payload 缺少 season")
        season = _integer(payload["season"], "season")
        if season is None:
            raise MetaSchemaError("Meta season 必须是整数")
        heroes_raw = payload.get("heroes")
        if not isinstance(heroes_raw, list):
            raise MetaSchemaError("Meta heroes 必须是数组")
        heroes = [_parse_hero_bucket(bucket, index) for index, bucket in enumerate(heroes_raw)]

        bans: list[RawBanRankBucket] | None
        if "bans" not in payload or payload["bans"] is None:
            bans = None
        elif not isinstance(payload["bans"], list):
            raise MetaSchemaError("Meta bans 必须是数组")
        else:
            bans = [_parse_ban_bucket(bucket, index) for index, bucket in enumerate(payload["bans"])]

        timestamp = payload.get("timestamp")
        if isinstance(timestamp, bool) or timestamp is not None and not isinstance(timestamp, (int, float, str)):
            raise MetaSchemaError("Meta timestamp 类型无效")
        if isinstance(timestamp, float) and not math.isfinite(timestamp):
            raise MetaSchemaError("Meta timestamp 必须是有限数值")

        return RawHeroMetaPayload(
            season=season,
            heroes=heroes,
            bans=bans,
            source_timestamp=timestamp,
            raw=copy.deepcopy(payload),
            fetched_at=datetime.now(timezone.utc),
            stale=False,
        )


def _integer(value: Any, field: str, *, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool):
        raise MetaSchemaError(f"Meta {field} 必须是整数")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise MetaSchemaError(f"Meta {field} 必须是整数，不能是小数")
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise MetaSchemaError(f"Meta {field} 必须是整数")
        try:
            return int(text)
        except ValueError as exc:
            raise MetaSchemaError(f"Meta {field} 必须是整数，不能是 {value!r}") from exc
    raise MetaSchemaError(f"Meta {field} 必须是整数")


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MetaSchemaError(f"Meta {field} 必须是对象")
    return value


def _rank(bucket: dict[str, Any], index: int) -> str:
    if "rank" not in bucket:
        raise MetaSchemaError(f"Meta rank bucket[{index}] 缺少 rank")
    value = bucket["rank"]
    if isinstance(value, bool) or value is None:
        raise MetaSchemaError(f"Meta rank bucket[{index}].rank 无效")
    if isinstance(value, (int, float)):
        normalized = _integer(value, f"rank bucket[{index}].rank")
        if normalized is None:
            raise MetaSchemaError(f"Meta rank bucket[{index}].rank 无效")
        if normalized != 0 and str(normalized) not in RANK_LABELS:
            raise MetaSchemaError(f"Meta rank bucket[{index}].rank 未知：{normalized}")
        return str(normalized)
    text = str(value).strip()
    if not text:
        raise MetaSchemaError(f"Meta rank bucket[{index}].rank 无效")
    if text != "0" and text not in RANK_LABELS:
        raise MetaSchemaError(f"Meta rank bucket[{index}].rank 未知：{text}")
    return text


def _parse_hero_bucket(value: Any, index: int) -> RawHeroRankBucket:
    bucket = _object(value, f"heroes[{index}]")
    rows = bucket.get("heroes")
    if not isinstance(rows, list):
        raise MetaSchemaError(f"Meta heroes[{index}].heroes 必须是数组")
    parsed: list[RawHeroMetaStat] = []
    fields = ("matches", "wins", "wr_matches", "wr_wins", "mirror_matches")
    for row_index, row_value in enumerate(rows):
        row = _object(row_value, f"heroes[{index}].heroes[{row_index}]")
        hero_id = _integer(row.get("hero_id"), "hero_id", nullable=True)
        values = {field: _integer(row.get(field), field) for field in fields}
        parsed.append(RawHeroMetaStat(hero_id=hero_id, **values))
    return RawHeroRankBucket(rank_code=_rank(bucket, index), heroes=parsed)


def _parse_ban_bucket(value: Any, index: int) -> RawBanRankBucket:
    bucket = _object(value, f"bans[{index}]")
    rows = bucket.get("bans")
    if not isinstance(rows, list):
        raise MetaSchemaError(f"Meta bans[{index}].bans 必须是数组")
    parsed: list[RawBanStat] = []
    for row_index, row_value in enumerate(rows):
        row = _object(row_value, f"bans[{index}].bans[{row_index}]")
        hero_id = _integer(row.get("hero_id"), "hero_id", nullable=True)
        parsed.append(RawBanStat(hero_id=hero_id, bans=_integer(row.get("bans"), "bans")))
    return RawBanRankBucket(rank_code=_rank(bucket, index), bans=parsed)
