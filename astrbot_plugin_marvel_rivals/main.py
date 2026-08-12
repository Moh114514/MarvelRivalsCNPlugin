from __future__ import annotations

import os
from pathlib import Path

from marvel_rivals_bot.datasource.base import DataSourceError
from marvel_rivals_bot.datasource.cn import CNDataSource
from marvel_rivals_bot.services.rivals import RivalsService
from marvel_rivals_bot.storage.bindings import BindingStore, BindingStoreError

try:
    from astrbot.api import logger
    from astrbot.api.event import AstrMessageEvent, filter
    from astrbot.api.star import Context, Star, register
except ImportError:  # Allows core modules and tests to run without AstrBot installed.
    logger = None
    AstrMessageEvent = object
    Context = object
    Star = object

    def register(*args, **kwargs):
        return lambda cls: cls

    class _Filter:
        def command(self, *_args, **_kwargs):
            return lambda func: func

    filter = _Filter()


@register("marvel_rivals", "MR-bot", "Marvel Rivals CN stats query", "0.2.0", "")
class MarvelRivalsPlugin(Star):
    def __init__(self, context: Context, config=None):
        if hasattr(super(), "__init__"):
            super().__init__(context)
        configured = dict(config or {})
        env_config = {key: value for key, value in os.environ.items() if key.startswith("MRCN_")}
        env_config.update(configured)
        self.source = CNDataSource(env=env_config)
        self.service = RivalsService(self.source, float(env_config.get("MRCN_CACHE_SECONDS", "60")))
        db_path = os.getenv("MRCN_BINDINGS_DB", "data/marvel_rivals.sqlite3")
        self.bindings = BindingStore(Path(db_path))

    def _qq_id(self, event: AstrMessageEvent) -> str:
        return str(event.get_sender_id())

    def _bound_uid(self, event: AstrMessageEvent) -> str | None:
        return self.bindings.get(self._qq_id(event))

    async def _query(self, event: AstrMessageEvent, uid: str | None):
        try:
            uid = uid or self._bound_uid(event)
        except BindingStoreError as exc:
            yield event.plain_result(str(exc))
            return
        if not uid:
            yield event.plain_result("请提供 UID，或先使用 /绑定漫威 <UID>")
            return
        try:
            yield event.plain_result(await self.service.player_text(uid))
        except DataSourceError as exc:
            if logger:
                logger.warning(str(exc))
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("漫威帮助")
    async def help(self, event: AstrMessageEvent):
        yield event.plain_result("漫威争锋查询：/绑定漫威 UID、/解绑漫威、/战绩 [UID]、/最近 [UID]")

    @filter.command("绑定漫威")
    async def bind(self, event: AstrMessageEvent, uid: str):
        if not uid.isdigit():
            yield event.plain_result("UID 必须是数字")
            return
        try:
            self.bindings.bind(self._qq_id(event), uid)
        except BindingStoreError as exc:
            yield event.plain_result(str(exc))
            return
        yield event.plain_result(f"已绑定漫威 UID：{uid}")

    @filter.command("解绑漫威")
    async def unbind(self, event: AstrMessageEvent):
        try:
            removed = self.bindings.unbind(self._qq_id(event))
        except BindingStoreError as exc:
            yield event.plain_result(str(exc))
            return
        yield event.plain_result("已解除绑定" if removed else "当前没有绑定")

    @filter.command("战绩")
    async def stats(self, event: AstrMessageEvent, uid: str = ""):
        async for result in self._query(event, uid.strip() or None):
            yield result

    @filter.command("查询")
    async def query(self, event: AstrMessageEvent, uid: str = ""):
        async for result in self._query(event, uid.strip() or None):
            yield result

    @filter.command("最近")
    async def recent(self, event: AstrMessageEvent, uid: str = ""):
        try:
            uid = uid.strip() or self._bound_uid(event)
        except BindingStoreError as exc:
            yield event.plain_result(str(exc))
            return
        if not uid:
            yield event.plain_result("请提供 UID，或先使用 /绑定漫威 <UID>")
            return
        try:
            yield event.plain_result(await self.service.matches_text(uid))
        except DataSourceError as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("英雄")
    async def hero(self, event: AstrMessageEvent, hero_id: str, uid: str = ""):
        try:
            uid = uid.strip() or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请提供 UID，或先绑定 UID")
                return
            yield event.plain_result(await self.service.hero_text(uid, hero_id))
        except (DataSourceError, BindingStoreError) as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("对局")
    async def match_detail(self, event: AstrMessageEvent, match_uid: str):
        try:
            yield event.plain_result(await self.service.match_detail_text(match_uid))
        except (DataSourceError, BindingStoreError) as exc:
            yield event.plain_result(f"查询失败：{exc}")
