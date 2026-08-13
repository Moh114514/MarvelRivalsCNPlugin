from __future__ import annotations

import os
from pathlib import Path

try:
    from .marvel_rivals_bot.datasource.base import DataSourceError
    from .marvel_rivals_bot.datasource.cn import CNDataSource
    from .marvel_rivals_bot.services.rivals import RivalsService
    from .marvel_rivals_bot.services.rivals import format_hero, format_match_detail, format_matches, format_player
    from .marvel_rivals_bot.storage.bindings import BindingStore, BindingStoreError
    from .qq_official import (
        QQOfficialCardSender, build_capability_test_card, build_hero_card,
        build_match_card, build_player_card, build_recent_card,
    )
    from .rendering import MatchImageRenderer
except ImportError:
    from marvel_rivals_bot.datasource.base import DataSourceError
    from marvel_rivals_bot.datasource.cn import CNDataSource
    from marvel_rivals_bot.services.rivals import RivalsService
    from marvel_rivals_bot.services.rivals import format_hero, format_match_detail, format_matches, format_player
    from marvel_rivals_bot.storage.bindings import BindingStore, BindingStoreError
    from qq_official import (
        QQOfficialCardSender, build_capability_test_card, build_hero_card,
        build_match_card, build_player_card, build_recent_card,
    )
    from rendering import MatchImageRenderer

try:
    from astrbot.api import logger
    from astrbot.api.event import AstrMessageEvent, filter
    from astrbot.api.star import Context, Star, register
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path
except ImportError:  # Allows core modules and tests to run without AstrBot installed.
    logger = None
    AstrMessageEvent = object
    Context = object
    Star = object
    get_astrbot_data_path = None

    def register(*args, **kwargs):
        return lambda cls: cls

    class _Filter:
        def command(self, *_args, **_kwargs):
            return lambda func: func

    filter = _Filter()


@register("marvel_rivals", "MR-bot", "Marvel Rivals CN stats query", "0.8.0", "")
class MarvelRivalsPlugin(Star):
    HELP_TEXT = """漫威争锋国服查询 | 指令帮助

【账号绑定】
/绑定漫威 <UID>
绑定当前 QQ 的游戏账号

/解绑漫威
解除当前 QQ 的游戏账号绑定

【数据查询】
/战绩 [UID] [赛季名称]
查询段位、综合数据和常用英雄

/查询 [UID] [赛季名称]
功能与 /战绩 相同

/最近 [UID] [赛季名称]
查询最近十场对局

/英雄 <英雄名称> [UID] [赛季名称]
查询指定英雄的赛季数据

/对局 <matchUid>
查询指定对局的详细数据

/卡片测试
验证 QQ Official Markdown、指令按钮和链接按钮能力

【参数说明】
绑定 UID 后，查询命令可以省略 UID。
赛季支持 S0、S9、S9.5、S9上半赛季、S9下半赛季，支持小写 s；S0 没有半赛季。
不填写赛季名称时使用插件配置的默认赛季。
已绑定 UID 时可以直接使用：/战绩 S9下半赛季。
对局命令可粘贴纯 ID，也可直接粘贴最近列表中的 matchUid=...。

【使用示例】
/战绩 1287101468 S9下半赛季
/最近 1287101468 s9.5
/英雄 蜘蛛侠 1287101468 s9"""

    def __init__(self, context: Context, config=None):
        if hasattr(super(), "__init__"):
            super().__init__(context)
        configured = dict(config or {})
        env_config = {key: value for key, value in os.environ.items() if key.startswith("MRCN_")}
        env_config.update(configured)
        self.source = CNDataSource(env=env_config)
        self.service = RivalsService(self.source, float(env_config.get("MRCN_CACHE_SECONDS", "60")))
        self.qq_card_sender = QQOfficialCardSender()
        self.image_renderer = MatchImageRenderer(self.html_render)
        db_path = os.getenv("MRCN_BINDINGS_DB")
        if not db_path:
            data_root = Path(get_astrbot_data_path()) if get_astrbot_data_path else Path("data")
            db_path = data_root / "plugin_data" / "astrbot_plugin_marvel_rivals" / "bindings.sqlite3"
        self.bindings = BindingStore(Path(db_path))

    def _qq_id(self, event: AstrMessageEvent) -> str:
        return str(event.get_sender_id())

    def _bound_uid(self, event: AstrMessageEvent) -> str | None:
        return self.bindings.get(self._qq_id(event))

    async def _send_card(self, event: AstrMessageEvent, builder, *args) -> bool:
        if not self.qq_card_sender.supports(event):
            return False
        try:
            await self.qq_card_sender.send(event, builder(*args))
            return True
        except Exception as exc:
            if logger:
                logger.warning(f"QQ Official 富消息构建或发送失败，回退普通文本：{exc}")
            return False

    @staticmethod
    def _uid_and_season(uid: str, season: str) -> tuple[str, str]:
        uid, season = uid.strip(), season.strip()
        if uid.lower().startswith("s") and not season:
            return "", uid
        return uid, season

    async def _query(self, event: AstrMessageEvent, uid: str | None, season: str | None = None):
        try:
            uid = uid or self._bound_uid(event)
        except BindingStoreError as exc:
            yield event.plain_result(str(exc))
            return
        if not uid:
            yield event.plain_result("请提供 UID，或先使用 /绑定漫威 <UID>")
            return
        try:
            stats = await self.service.get_player_stats(uid, season)
            if not await self._send_card(event, build_player_card, stats):
                yield event.plain_result(format_player(stats))
        except DataSourceError as exc:
            if logger:
                logger.warning(str(exc))
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("漫威帮助")
    async def help(self, event: AstrMessageEvent):
        """显示漫威争锋查询插件的完整指令帮助。"""
        yield event.plain_result(self.HELP_TEXT)

    @filter.command("绑定漫威")
    async def bind(self, event: AstrMessageEvent, uid: str):
        """绑定当前 QQ 对应的漫威争锋 UID。"""
        if not uid.isdigit():
            yield event.plain_result("UID 必须是数字")
            return
        try:
            await self.source.validate_uid(uid)
            self.bindings.bind(self._qq_id(event), uid)
        except (DataSourceError, BindingStoreError) as exc:
            yield event.plain_result(str(exc))
            return
        yield event.plain_result(f"已绑定漫威 UID：{uid}")

    @filter.command("解绑漫威")
    async def unbind(self, event: AstrMessageEvent):
        """解除当前 QQ 已绑定的漫威争锋 UID。"""
        try:
            removed = self.bindings.unbind(self._qq_id(event))
        except BindingStoreError as exc:
            yield event.plain_result(str(exc))
            return
        yield event.plain_result("已解除绑定" if removed else "当前没有绑定")

    @filter.command("战绩")
    async def stats(self, event: AstrMessageEvent, uid: str = "", season: str = ""):
        """查询玩家段位、综合数据和常用英雄，可指定 UID 和赛季名称。"""
        uid, season = self._uid_and_season(uid, season)
        async for result in self._query(event, uid or None, season or None):
            yield result

    @filter.command("查询")
    async def query(self, event: AstrMessageEvent, uid: str = "", season: str = ""):
        """查询玩家战绩，功能与 /战绩 相同。"""
        uid, season = self._uid_and_season(uid, season)
        async for result in self._query(event, uid or None, season or None):
            yield result

    @filter.command("最近")
    async def recent(self, event: AstrMessageEvent, uid: str = "", season: str = ""):
        """查询玩家最近十场对局，可指定 UID 和赛季名称。"""
        uid, season = self._uid_and_season(uid, season)
        try:
            uid = uid or self._bound_uid(event)
        except BindingStoreError as exc:
            yield event.plain_result(str(exc))
            return
        if not uid:
            yield event.plain_result("请提供 UID，或先使用 /绑定漫威 <UID>")
            return
        try:
            season_code = self.service.season_code(season or None)
            matches = await self.service.get_recent_matches(uid, season or None)
            try:
                image_url = await self.image_renderer.recent(uid, season_code, matches)
                yield event.image_result(image_url)
            except Exception as exc:
                if logger:
                    logger.warning(f"最近对局图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(format_matches(matches, season_code))
                return
            if self.qq_card_sender.supports(event):
                await self._send_card(event, build_recent_card, uid, season_code, matches)
        except DataSourceError as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("英雄")
    async def hero(self, event: AstrMessageEvent, hero_name: str, uid: str = "", season: str = ""):
        """使用中文英雄名称查询指定英雄的赛季数据。"""
        uid, season = self._uid_and_season(uid, season)
        try:
            uid = uid or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请提供 UID，或先绑定 UID")
                return
            result = await self.service.get_hero_stats(uid, hero_name, season or None)
            if not await self._send_card(event, build_hero_card, result):
                yield event.plain_result(format_hero(result.payload, result.season))
        except (DataSourceError, BindingStoreError) as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("对局")
    async def match_detail(self, event: AstrMessageEvent, match_uid: str):
        """使用 matchUid 查询详情，支持纯 ID 或 matchUid=... 格式。"""
        try:
            payload = await self.service.get_match_detail(match_uid)
            try:
                image_url = await self.image_renderer.detail(payload)
                yield event.image_result(image_url)
            except Exception as exc:
                if logger:
                    logger.warning(f"对局详情图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(format_match_detail(payload))
                return
            if self.qq_card_sender.supports(event):
                await self._send_card(event, build_match_card, payload)
        except (DataSourceError, BindingStoreError) as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("卡片测试")
    async def card_test(self, event: AstrMessageEvent):
        """验证 QQ Official 原生 Markdown 和消息按钮能力。"""
        try:
            await self.qq_card_sender.send(event, build_capability_test_card())
        except Exception as exc:
            if logger:
                logger.warning(f"QQ Official 富消息能力测试失败：{exc}")
            yield event.plain_result(
                "QQ Official 富消息发送失败，已回退普通文本。\n"
                "请确认当前适配器为 QQ Official，且机器人账号拥有 Markdown 与消息按钮权限。"
            )
