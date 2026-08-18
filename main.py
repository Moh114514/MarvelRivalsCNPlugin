from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

try:
    from .marvel_rivals_bot.datasource.base import DataSourceError
    from .marvel_rivals_bot.datasource.cn import CNDataSource
    from .marvel_rivals_bot.services.rivals import RivalsService
    from .marvel_rivals_bot.services.rivals import format_hero_result, format_match_detail, format_matches, format_player
    from .marvel_rivals_bot.storage.bindings import BindingStore, BindingStoreError
    from .marvel_rivals_bot.meta.commands import (
        parse_historical_meta_command_args,
        parse_meta_command_args,
    )
    from .marvel_rivals_bot.meta.errors import MetaDataSourceError
    from .marvel_rivals_bot.meta.formatters import (
        format_hero_meta_board,
        format_hero_meta_comparison,
        format_hero_meta_overview,
        format_hero_meta_segments,
        format_hero_meta_trend,
        format_meta_insights,
        format_meta_version_changes,
        format_rank_monsters,
        format_single_hero_meta,
    )
    from .marvel_rivals_bot.meta.service import MetaService
    from .marvel_rivals_bot.meta.sources.rivalsmeta import RivalsMetaSource
    from .marvel_rivals_bot.analytics.commands import parse_player_meta_args
    from .marvel_rivals_bot.analytics.formatters import (
        format_player_environment,
        format_player_hero_pool,
        format_player_signature,
    )
    from .marvel_rivals_bot.analytics.player_meta import PlayerMetaQueryError, PlayerMetaService
    from .qq_official import (
        QQOfficialCardSender, build_capability_test_card, build_recent_card,
    )
    from .rendering import AssetManager, MatchImageRenderer
except ImportError:
    # AstrBot also supports loading a plugin's main.py with its directory on
    # sys.path instead of importing it as a package.
    from marvel_rivals_bot.datasource.base import DataSourceError
    from marvel_rivals_bot.datasource.cn import CNDataSource
    from marvel_rivals_bot.services.rivals import RivalsService
    from marvel_rivals_bot.services.rivals import format_hero_result, format_match_detail, format_matches, format_player
    from marvel_rivals_bot.storage.bindings import BindingStore, BindingStoreError
    from marvel_rivals_bot.meta.commands import (
        parse_historical_meta_command_args,
        parse_meta_command_args,
    )
    from marvel_rivals_bot.meta.errors import MetaDataSourceError
    from marvel_rivals_bot.meta.formatters import (
        format_hero_meta_board,
        format_hero_meta_comparison,
        format_hero_meta_overview,
        format_hero_meta_segments,
        format_hero_meta_trend,
        format_meta_insights,
        format_meta_version_changes,
        format_rank_monsters,
        format_single_hero_meta,
    )
    from marvel_rivals_bot.meta.service import MetaService
    from marvel_rivals_bot.meta.sources.rivalsmeta import RivalsMetaSource
    from marvel_rivals_bot.analytics.commands import parse_player_meta_args
    from marvel_rivals_bot.analytics.formatters import (
        format_player_environment,
        format_player_hero_pool,
        format_player_signature,
    )
    from marvel_rivals_bot.analytics.player_meta import PlayerMetaQueryError, PlayerMetaService
    from qq_official import (
        QQOfficialCardSender, build_capability_test_card, build_recent_card,
    )
    from rendering import AssetManager, MatchImageRenderer

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


@register("marvel_rivals", "MR-bot", "Marvel Rivals CN stats query", "0.14.13", "")
class MarvelRivalsPlugin(Star):
    HELP_TEXT = """漫威争锋国服查询 | 指令帮助

/帮助
显示完整指令帮助

/绑定账号 <UID>
绑定游戏账号（兼容 /绑定漫威）

/解绑账号
解除账号绑定（兼容 /解绑漫威）

/查询 [UID] [赛季]
查询个人资料（含快速与竞技数据）

/最近对局 [UID] [赛季]
查询最近十场（兼容 /最近）

/英雄数据 <名称> [UID] [赛季]
查询英雄数据（兼容 /英雄）

/对局详情 <matchUid>
查询对局详情（兼容 /对局）

/卡片测试
测试 QQ 卡片能力

/英雄环境 [段位] [赛季]
查询全局英雄环境总览（默认全段位；不接受排序指标；默认生成图片）

/英雄排行 <胜率|选取率|Ban率|场次> [段位] [赛季]
按指定指标查询英雄排行（必须且只能指定一个排序指标；默认生成图片）

/英雄统计 <英雄名称> [段位] [赛季]
查询单个英雄的全局环境数据（不接受排序指标；默认生成图片）

/英雄分段 <英雄名称> [赛季]
查询一个英雄在九个大段位中的环境数据（默认生成图片）

/英雄对比 <英雄1> <英雄2> [段位] [赛季]
对比同一环境中的两个英雄（默认生成图片）

/英雄趋势 <英雄名称> [段位] [赛季...]
查询英雄跨赛季的胜率、选取率、Ban 率和样本变化（默认最近四个赛季）

/版本变化 <旧赛季> <新赛季> [段位]
比较两个赛季快照的胜率、选取率和 Ban 率变化（默认生成图片）

/版本黑马 [段位] [旧赛季] [新赛季]
按透明规则查询赛季黑马（默认当前赛季与上一赛季）

/冷门强者 [段位] [赛季]
查询高胜率、低选取率且低 Ban 率的英雄（青铜/白银不计算 Ban 率）

/热门低胜率 [段位] [赛季]
查询高选取率但低胜率的英雄（兼容 /热门陷阱）

/分段怪物 [赛季]
按段位顺序列出相对自身全段位胜率高至少 2pp 的英雄，不进行跨段位排名

段位支持全段位、钻石+、大师+、天神+、永恒+；已绑定账号可省略 UID；赛季支持 S0、S9、S9.5、S9上半赛季、S9下半赛季。"""

    HELP_TEXT += """

/我的环境 [UID] [赛季]
根据已绑定账号的当前段位，查看同段位英雄环境

/我的英雄池 [UID] [赛季]
按快速与竞技总场次查看英雄池，并核对竞技表现

/我的绝活 [UID] [赛季] [最低总场次]
查看满足总场次、竞技至少 5 场和同段位表现要求的英雄；可用数字参数调整最低总场次，默认 20
"""

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
        data_root = Path(get_astrbot_data_path()) if get_astrbot_data_path else Path("data")
        plugin_data_root = data_root / "plugin_data" / "astrbot_plugin_marvel_rivals"
        asset_root = env_config.get("MRCN_ASSET_CACHE_DIR") or plugin_data_root / "assets"
        verify_value = str(env_config.get("MRCN_VERIFY_SSL", "true")).lower()
        verify_ssl: bool | str = verify_value not in {"0", "false", "no"}
        ca_cert = str(env_config.get("MRCN_CA_CERT", "")).strip()
        if ca_cert:
            verify_ssl = ca_cert
        self.asset_manager = AssetManager(
            asset_root,
            timeout_seconds=float(
                env_config.get(
                    "MRCN_ASSET_TIMEOUT_SECONDS",
                    env_config.get("MRCN_TIMEOUT_SECONDS", "10"),
                )
            ),
            refresh_days=float(env_config.get("MRCN_ASSET_REFRESH_DAYS", "30")),
            max_concurrency=int(env_config.get("MRCN_ASSET_MAX_CONCURRENCY", "4")),
            verify_ssl=verify_ssl,
            proxy=str(env_config.get("MRCN_PROXY", "")).strip() or None,
            trust_env=str(env_config.get("MRCN_TRUST_ENV", "false")).lower() in {"1", "true", "yes"},
        )
        if not self.asset_manager.available and logger:
            logger.warning("英雄素材缓存目录不可用，图片功能将回退 CSS-only")
        db_path = os.getenv("MRCN_BINDINGS_DB")
        if not db_path:
            db_path = plugin_data_root / "bindings.sqlite3"
        self.bindings = BindingStore(Path(db_path))
        self.meta_enabled = str(env_config.get("MRCN_META_ENABLED", "true")).lower() not in {"0", "false", "no", "off"}
        self.meta_source = None
        self.meta_service = None
        if self.meta_enabled:
            try:
                fresh_seconds = float(env_config.get("MRCN_META_CACHE_SECONDS", "600"))
                stale_seconds = float(env_config.get("MRCN_META_STALE_SECONDS", "86400"))
                if stale_seconds < fresh_seconds:
                    stale_seconds = fresh_seconds
                self.meta_source = RivalsMetaSource(env=env_config)
                self.meta_service = MetaService(
                    self.meta_source,
                    cache_root=plugin_data_root,
                    fresh_seconds=fresh_seconds,
                    stale_seconds=stale_seconds,
                    default_season=str(env_config.get("MRCN_DEFAULT_SEASON", "19")),
                )
            except (MetaDataSourceError, TypeError, ValueError) as exc:
                self.meta_enabled = False
                if logger:
                    logger.warning(f"Meta 功能初始化失败，将保持关闭：{exc}")

        self.player_meta_service = (
            PlayerMetaService(self.service, self.meta_service)
            if self.meta_service is not None
            else None
        )

    def _qq_id(self, event: AstrMessageEvent) -> str:
        return str(event.get_sender_id())

    def _bound_uid(self, event: AstrMessageEvent) -> str | None:
        return self.bindings.get(self._qq_id(event))

    async def _send_card(self, event: AstrMessageEvent, builder, *args, image_url: str | None = None) -> bool:
        if not self.qq_card_sender.supports(event):
            return False
        try:
            card = builder(*args)
            if image_url:
                card = replace(card, image_url=image_url)
            await self.qq_card_sender.send(event, card)
            return True
        except Exception as exc:
            if logger:
                logger.warning(f"QQ Official 富消息构建或发送失败，回退普通文本：{exc}")
            return False

    async def _send_image(self, event: AstrMessageEvent, image_url: str) -> bool:
        if not self.qq_card_sender.supports(event):
            return False
        try:
            await self.qq_card_sender.send_image(event, image_url)
            return True
        except Exception as exc:
            if logger:
                logger.warning(f"QQ Official 图片发送失败，回退普通文本：{exc}")
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
            try:
                image_url = await self.image_renderer.player(stats)
            except Exception as exc:
                if logger:
                    logger.warning(f"玩家战绩图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(format_player(stats))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(format_player(stats))
            else:
                yield event.image_result(image_url)
        except DataSourceError as exc:
            if logger:
                logger.warning(str(exc))
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("帮助")
    async def help(self, event: AstrMessageEvent):
        """显示漫威争锋查询插件的完整指令帮助。"""
        try:
            image_url = await self.image_renderer.help(self.HELP_TEXT)
        except Exception as exc:
            if logger:
                logger.warning(f"帮助图片渲染失败，回退普通文本：{exc}")
            yield event.plain_result(self.HELP_TEXT)
            return
        if self.qq_card_sender.supports(event):
            if not await self._send_image(event, image_url):
                yield event.plain_result(self.HELP_TEXT)
        else:
            yield event.image_result(image_url)

    @filter.command("漫威帮助")
    async def help_legacy(self, event: AstrMessageEvent):
        """兼容旧版 /漫威帮助 指令。"""
        async for result in self.help(event):
            yield result

    @filter.command("绑定账号")
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

    @filter.command("绑定漫威")
    async def bind_legacy(self, event: AstrMessageEvent, uid: str):
        """兼容旧版 /绑定漫威 指令。"""
        async for result in self.bind(event, uid):
            yield result

    @filter.command("解绑账号")
    async def unbind(self, event: AstrMessageEvent):
        """解除当前 QQ 已绑定的漫威争锋 UID。"""
        try:
            removed = self.bindings.unbind(self._qq_id(event))
        except BindingStoreError as exc:
            yield event.plain_result(str(exc))
            return
        yield event.plain_result("已解除绑定" if removed else "当前没有绑定")

    @filter.command("解绑漫威")
    async def unbind_legacy(self, event: AstrMessageEvent):
        """兼容旧版 /解绑漫威 指令。"""
        async for result in self.unbind(event):
            yield result

    @filter.command("战绩")
    async def stats(self, event: AstrMessageEvent, uid: str = "", season: str = ""):
        """兼容旧版 /战绩 命令；正式入口为 /查询。"""
        uid, season = self._uid_and_season(uid, season)
        async for result in self._query(event, uid or None, season or None):
            yield result

    @filter.command("查询")
    async def query(self, event: AstrMessageEvent, uid: str = "", season: str = ""):
        """查询玩家个人资料，包含快速、竞技和总计数据。"""
        uid, season = self._uid_and_season(uid, season)
        async for result in self._query(event, uid or None, season or None):
            yield result

    @filter.command("最近对局")
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
            except Exception as exc:
                if logger:
                    logger.warning(f"最近对局图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(format_matches(matches, season_code))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_card(event, build_recent_card, uid, season_code, matches, image_url=image_url):
                    yield event.plain_result(format_matches(matches, season_code))
            else:
                yield event.image_result(image_url)
        except DataSourceError as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("最近")
    async def recent_legacy(self, event: AstrMessageEvent, uid: str = "", season: str = ""):
        """兼容旧版 /最近 指令。"""
        async for result in self.recent(event, uid, season):
            yield result

    @filter.command("英雄数据")
    async def hero(self, event: AstrMessageEvent, hero_name: str, uid: str = "", season: str = ""):
        """使用中文英雄名称查询指定英雄的赛季数据。"""
        uid, season = self._uid_and_season(uid, season)
        try:
            uid = uid or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请提供 UID，或先绑定 UID")
                return
            result = await self.service.get_hero_stats(uid, hero_name, season or None)
            try:
                image_url = await self.image_renderer.hero(result)
            except Exception as exc:
                if logger:
                    logger.warning(f"英雄数据图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(format_hero_result(result))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(format_hero_result(result))
            else:
                yield event.image_result(image_url)
        except (DataSourceError, BindingStoreError) as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("英雄")
    async def hero_legacy(self, event: AstrMessageEvent, hero_name: str, uid: str = "", season: str = ""):
        """兼容旧版 /英雄 指令。"""
        async for result in self.hero(event, hero_name, uid, season):
            yield result

    @filter.command("对局详情")
    async def match_detail(self, event: AstrMessageEvent, match_uid: str):
        """使用 matchUid 查询详情，支持纯 ID 或 matchUid=... 格式。"""
        try:
            payload = await self.service.get_match_detail(match_uid)
            try:
                image_url = await self.image_renderer.detail(payload)
            except Exception as exc:
                if logger:
                    logger.warning(f"对局详情图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(format_match_detail(payload))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(format_match_detail(payload))
            else:
                yield event.image_result(image_url)
        except (DataSourceError, BindingStoreError) as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("对局")
    async def match_detail_legacy(self, event: AstrMessageEvent, match_uid: str):
        """兼容旧版 /对局 指令。"""
        async for result in self.match_detail(event, match_uid):
            yield result

    def _meta_unavailable(self) -> str:
        return "当前未启用英雄环境功能"

    def _meta_source_failure(self, error: MetaDataSourceError) -> str:
        if logger:
            logger.warning(f"Meta 数据源错误：{type(error).__name__}")
        return "查询失败：英雄环境数据源暂时不可用，请稍后重试"

    async def _render_meta_result(self, event, model, fallback: str, renderer) -> object | None:
        try:
            image_url = await renderer(model)
        except Exception as exc:
            if logger:
                logger.warning(f"Meta 图片渲染失败，回退普通文本：{exc}")
            return event.plain_result(fallback)
        if self.qq_card_sender.supports(event):
            if not await self._send_image(event, image_url):
                return event.plain_result(fallback)
            return None
        return event.image_result(image_url)

    @filter.command("英雄环境")
    async def hero_meta(self, event: AstrMessageEvent, arg1: str = "", arg2: str = "", arg3: str = ""):
        """查询指定赛季和段位的全局英雄环境，不接受排序指标。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_meta_command_args(arg1, arg2, arg3, allow_sort=False)
            overview = await self.meta_service.get_hero_meta_overview(
                season=args.season,
                rank=args.rank,
                limit=5,
            )
            fallback = format_hero_meta_overview(overview)
            try:
                image_url = await self.image_renderer.meta_overview(overview)
            except Exception as exc:
                if logger:
                    logger.warning(f"英雄环境图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(fallback)
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield event.image_result(image_url)
        except ValueError as exc:
            yield event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("英雄排行")
    async def hero_meta_rank(self, event: AstrMessageEvent, arg1: str = "", arg2: str = "", arg3: str = ""):
        """按一个胜率、选取率、Ban率或场次指标查询英雄排行，不接受英雄名称。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_meta_command_args(
                arg1,
                arg2,
                arg3,
                require_sort=True,
            )
            board = await self.meta_service.get_hero_meta_board(
                season=args.season,
                rank=args.rank,
                sort_by=args.sort_by,
                limit=10,
            )
            fallback = format_hero_meta_board(board)
            try:
                image_url = await self.image_renderer.meta_board(board)
            except Exception as exc:
                if logger:
                    logger.warning(f"英雄排行图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(fallback)
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield event.image_result(image_url)
        except ValueError as exc:
            yield event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("英雄统计")
    async def hero_meta_stats(self, event: AstrMessageEvent, hero_name: str = "", arg2: str = "", arg3: str = ""):
        """使用中文英雄名称查询全局环境统计，不接受排序指标。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_meta_command_args(
                hero_name,
                arg2,
                arg3,
                require_hero=True,
                allow_sort=False,
            )
            board = await self.meta_service.get_single_hero_meta_board(
                args.hero_name or "",
                season=args.season,
                rank=args.rank,
            )
            result = board.heroes[0]
            fallback = format_single_hero_meta(
                result,
                season_label=board.season_label,
                rank_label=board.rank_label,
                source=board.source,
                source_timestamp=board.source_timestamp,
                stale=board.stale,
            )
            try:
                image_url = await self.image_renderer.meta_single(board)
            except Exception as exc:
                if logger:
                    logger.warning(f"英雄统计图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(fallback)
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield event.image_result(image_url)
        except ValueError as exc:
            yield event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("英雄分段")
    async def hero_meta_segments(self, event: AstrMessageEvent, arg1: str = "", arg2: str = "", arg3: str = ""):
        """查询一个英雄在九个 Meta 大段位中的环境数据，不接受段位筛选。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_meta_command_args(
                arg1,
                arg2,
                arg3,
                require_hero=True,
                allow_sort=False,
                allow_rank=False,
            )
            segments = await self.meta_service.get_hero_meta_segments(
                args.hero_name or "",
                season=args.season,
            )
            fallback = format_hero_meta_segments(segments)
            try:
                image_url = await self.image_renderer.meta_segments(segments)
            except Exception as exc:
                if logger:
                    logger.warning(f"英雄分段图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(fallback)
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield event.image_result(image_url)
        except ValueError as exc:
            yield event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("英雄对比")
    async def hero_meta_comparison(
        self,
        event: AstrMessageEvent,
        arg1: str = "",
        arg2: str = "",
        arg3: str = "",
        arg4: str = "",
    ):
        """对比同一赛季和段位中的两个中文英雄，不接受排序指标。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_meta_command_args(
                arg1,
                arg2,
                arg3,
                arg4,
                require_hero_count=2,
                allow_sort=False,
            )
            comparison = await self.meta_service.get_hero_meta_comparison(
                args.hero_names[0],
                args.hero_names[1],
                season=args.season,
                rank=args.rank,
            )
            fallback = format_hero_meta_comparison(comparison)
            try:
                image_url = await self.image_renderer.meta_comparison(comparison)
            except Exception as exc:
                if logger:
                    logger.warning(f"英雄对比图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(fallback)
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield event.image_result(image_url)
        except ValueError as exc:
            yield event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("英雄趋势")
    async def hero_meta_trend(
        self,
        event: AstrMessageEvent,
        arg1: str = "",
        arg2: str = "",
        arg3: str = "",
        arg4: str = "",
        arg5: str = "",
        arg6: str = "",
    ):
        """查询一个英雄跨多个赛季的环境趋势。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_historical_meta_command_args(
                arg1, arg2, arg3, arg4, arg5, arg6, require_hero=True
            )
            series = await self.meta_service.get_hero_meta_trend(
                args.hero_name or "",
                seasons=args.seasons or None,
                rank=args.rank,
            )
            fallback = format_hero_meta_trend(series)
            result = await self._render_meta_result(event, series, fallback, self.image_renderer.meta_trend)
            if result is not None:
                yield result
        except ValueError as exc:
            yield event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("版本变化")
    async def meta_version_changes(
        self,
        event: AstrMessageEvent,
        arg1: str = "",
        arg2: str = "",
        arg3: str = "",
    ):
        """比较两个赛季快照的英雄环境变化。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_historical_meta_command_args(arg1, arg2, arg3, min_seasons=2, max_seasons=2)
            changes = await self.meta_service.get_meta_version_changes(
                args.seasons[0], args.seasons[1], rank=args.rank
            )
            fallback = format_meta_version_changes(changes)
            result = await self._render_meta_result(
                event, changes, fallback, self.image_renderer.meta_version_changes
            )
            if result is not None:
                yield result
        except ValueError as exc:
            yield event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("版本黑马")
    async def meta_black_horse(
        self,
        event: AstrMessageEvent,
        arg1: str = "",
        arg2: str = "",
        arg3: str = "",
    ):
        """按透明阈值查询当前赛季相对上一赛季的黑马。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_historical_meta_command_args(arg1, arg2, arg3, max_seasons=2)
            previous = args.seasons[0] if len(args.seasons) == 2 else None
            current = args.seasons[-1] if args.seasons else None
            insights = await self.meta_service.get_meta_insights(
                "black_horse",
                season=current,
                previous_season=previous,
                rank=args.rank,
            )
            fallback = format_meta_insights(insights)
            result = await self._render_meta_result(
                event, insights, fallback, self.image_renderer.meta_insights
            )
            if result is not None:
                yield result
        except ValueError as exc:
            yield event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    async def _meta_filter_insight(self, event, insight_type: str, *parts: str):
        if self.meta_service is None:
            return event.plain_result(self._meta_unavailable())
        try:
            args = parse_historical_meta_command_args(*parts, max_seasons=1)
            insights = await self.meta_service.get_meta_insights(
                insight_type,
                season=args.seasons[0] if args.seasons else None,
                rank=args.rank,
            )
            fallback = format_meta_insights(insights)
            return await self._render_meta_result(event, insights, fallback, self.image_renderer.meta_insights)
        except ValueError as exc:
            return event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            return event.plain_result(self._meta_source_failure(exc))

    @filter.command("冷门强者")
    async def meta_cold_strong(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """查询高胜率且低选取率的英雄。"""
        result = await self._meta_filter_insight(event, "cold_strong", arg1, arg2)
        if result is not None:
            yield result

    @filter.command("热门低胜率", alias={"热门陷阱"})
    async def meta_hot_trap(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """查询高选取率但低胜率的英雄。"""
        result = await self._meta_filter_insight(event, "hot_trap", arg1, arg2)
        if result is not None:
            yield result

    @filter.command("分段怪物")
    async def meta_rank_monsters(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """查询各段位中相对全段位表现突出的英雄。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_historical_meta_command_args(arg1, arg2, allow_rank=False, max_seasons=1)
            board = await self.meta_service.get_rank_monsters(
                season=args.seasons[0] if args.seasons else None,
            )
            fallback = format_rank_monsters(board)
            result = await self._render_meta_result(event, board, fallback, self.image_renderer.rank_monsters)
            if result is not None:
                yield result
        except ValueError as exc:
            yield event.plain_result(f"参数错误：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("我的环境")
    async def my_environment(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """根据 UID 或已绑定账号的当前段位查询同段位英雄环境。"""
        if self.player_meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_player_meta_args(arg1, arg2, allow_uid=True)
            uid = args.uid or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请先使用 /绑定账号 <UID>，或直接提供 UID")
                return
            profile = await self.player_meta_service.get_player_environment(uid, season=args.season)
            fallback = format_player_environment(profile)
            try:
                image_url = await self.image_renderer.player_meta_environment(profile)
            except Exception as exc:
                if logger:
                    logger.warning(f"我的环境图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(fallback)
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield event.image_result(image_url)
        except (ValueError, DataSourceError) as exc:
            yield event.plain_result(f"查询失败：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("我的英雄池")
    async def my_hero_pool(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """对比 UID 或已绑定账号的常用英雄与同段位 Meta。"""
        if self.player_meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_player_meta_args(arg1, arg2, allow_uid=True)
            uid = args.uid or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请先使用 /绑定账号 <UID>，或直接提供 UID")
                return
            profile = await self.player_meta_service.get_player_hero_pool(uid, season=args.season)
            fallback = format_player_hero_pool(profile)
            try:
                image_url = await self.image_renderer.player_hero_pool(profile)
            except Exception as exc:
                if logger:
                    logger.warning(f"我的英雄池图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(fallback)
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield event.image_result(image_url)
        except (ValueError, DataSourceError) as exc:
            yield event.plain_result(f"查询失败：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("我的绝活")
    async def my_signature(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """查询个人英雄胜率高于同段位环境的英雄，可用数字参数调整最低总场次。"""
        if self.player_meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_player_meta_args(
                arg1, arg2, allow_minimum_matches=True, allow_uid=True
            )
            uid = args.uid or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请先使用 /绑定账号 <UID>，或直接提供 UID")
                return
            signature_kwargs = {"season": args.season}
            if args.minimum_matches_provided:
                signature_kwargs["minimum_matches"] = args.minimum_matches
            profile = await self.player_meta_service.get_player_signature(uid, **signature_kwargs)
            fallback = format_player_signature(profile)
            try:
                image_url = await self.image_renderer.player_signature(profile)
            except Exception as exc:
                if logger:
                    logger.warning(f"我的绝活图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(fallback)
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield event.image_result(image_url)
        except (ValueError, DataSourceError) as exc:
            yield event.plain_result(f"查询失败：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

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
