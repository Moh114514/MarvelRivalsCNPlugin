from __future__ import annotations

import os
from time import perf_counter
from dataclasses import replace
from collections.abc import Mapping
from pathlib import Path

try:
    from .marvel_rivals_bot.datasource.base import DataSourceError
    from .marvel_rivals_bot.datasource.cn import CNDataSource
    from .marvel_rivals_bot.commands.time_window import (
        MatchWindowCommandUsageError,
        parse_match_window_command_args,
    )
    from .marvel_rivals_bot.services.rivals import RivalsService
    from .marvel_rivals_bot.services.match_history import MatchHistoryService
    from .marvel_rivals_bot.services.rivals import (
        format_hero_result,
        format_match_detail,
        format_matches,
        format_match_window,
        format_player,
    )
    from .marvel_rivals_bot.storage.bindings import BindingStore, BindingStoreError
    from .marvel_rivals_bot.meta.commands import (
        CommandUsageError,
        parse_historical_meta_command_args,
        parse_meta_command_args,
    )
    from .marvel_rivals_bot.meta.errors import MetaDataSourceError
    from .marvel_rivals_bot.meta.formatters import (
        format_hero_meta_board,
        format_hero_meta_comparison,
        format_hero_meta_overview,
        format_hero_meta_role_boards,
        format_hero_meta_segments,
        format_hero_meta_trend,
        format_meta_insights,
        format_meta_version_changes,
        format_rank_monsters,
        format_single_hero_meta,
    )
    from .marvel_rivals_bot.meta.service import MetaService
    from .marvel_rivals_bot.meta.sources.rivalsmeta import RivalsMetaSource
    from .marvel_rivals_bot.analytics.commands import (
        parse_player_analysis_args,
        parse_player_meta_args,
    )
    from .marvel_rivals_bot.analytics.formatters import (
        format_player_environment,
        format_player_hero_pool_analysis,
        format_player_hero_analysis,
        format_player_signature,
        format_player_sickness,
    )
    from .marvel_rivals_bot.analytics.player_meta import PlayerMetaQueryError, PlayerMetaService
    from .marvel_rivals_bot.analytics.models import AnalysisScope
    from .marvel_rivals_bot.reference.seasons import parse_season_name
    from .marvel_rivals_bot.analytics.signature import PlayerCareerAnalysisService, PlayerSignatureService
    from .qq_official import (
        QQOfficialCardSender, build_capability_test_card, build_match_window_card, build_recent_card,
    )
    from .rendering import AssetManager, MatchImageRenderer
    from .messaging import OneBotSender, SenderRouter
    from .marvel_rivals_bot.storage.interaction_sessions import InteractionSessionStore
except ImportError:
    # AstrBot also supports loading a plugin's main.py with its directory on
    # sys.path instead of importing it as a package.
    from marvel_rivals_bot.datasource.base import DataSourceError
    from marvel_rivals_bot.datasource.cn import CNDataSource
    from marvel_rivals_bot.commands.time_window import (
        MatchWindowCommandUsageError,
        parse_match_window_command_args,
    )
    from marvel_rivals_bot.services.rivals import RivalsService
    from marvel_rivals_bot.services.match_history import MatchHistoryService
    from marvel_rivals_bot.services.rivals import (
        format_hero_result,
        format_match_detail,
        format_matches,
        format_match_window,
        format_player,
    )
    from marvel_rivals_bot.storage.bindings import BindingStore, BindingStoreError
    from marvel_rivals_bot.meta.commands import (
        CommandUsageError,
        parse_historical_meta_command_args,
        parse_meta_command_args,
    )
    from marvel_rivals_bot.meta.errors import MetaDataSourceError
    from marvel_rivals_bot.meta.formatters import (
        format_hero_meta_board,
        format_hero_meta_comparison,
        format_hero_meta_overview,
        format_hero_meta_role_boards,
        format_hero_meta_segments,
        format_hero_meta_trend,
        format_meta_insights,
        format_meta_version_changes,
        format_rank_monsters,
        format_single_hero_meta,
    )
    from marvel_rivals_bot.meta.service import MetaService
    from marvel_rivals_bot.meta.sources.rivalsmeta import RivalsMetaSource
    from marvel_rivals_bot.analytics.commands import (
        parse_player_analysis_args,
        parse_player_meta_args,
    )
    from marvel_rivals_bot.analytics.formatters import (
        format_player_environment,
        format_player_hero_pool_analysis,
        format_player_hero_analysis,
        format_player_signature,
        format_player_sickness,
    )
    from marvel_rivals_bot.analytics.player_meta import PlayerMetaQueryError, PlayerMetaService
    from marvel_rivals_bot.analytics.models import AnalysisScope
    from marvel_rivals_bot.reference.seasons import parse_season_name
    from marvel_rivals_bot.analytics.signature import PlayerCareerAnalysisService, PlayerSignatureService
    from qq_official import (
        QQOfficialCardSender, build_capability_test_card, build_match_window_card, build_recent_card,
    )
    from rendering import AssetManager, MatchImageRenderer
    from messaging import OneBotSender, SenderRouter
    from marvel_rivals_bot.storage.interaction_sessions import InteractionSessionStore

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
        def __init__(self):
            self.registered_commands = []

        def command(self, name, *args, alias=None, **kwargs):
            def decorator(func):
                self.registered_commands.append({
                    "name": name,
                    "aliases": frozenset(alias or ()),
                    "handler": func,
                })
                return func

            return decorator

    filter = _Filter()


def _safe_int_config(config: dict, key: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(config.get(key, default))
        if value < minimum:
            raise ValueError
        return value
    except (TypeError, ValueError):
        if logger:
            logger.warning(f"配置 {key} 无效，已使用安全默认值 {default}")
        return default


def _safe_float_config(config: dict, key: str, default: float, minimum: float = 0.0) -> float:
    try:
        value = float(config.get(key, default))
        if value < minimum:
            raise ValueError
        return value
    except (TypeError, ValueError):
        if logger:
            logger.warning(f"配置 {key} 无效，已使用安全默认值 {default}")
        return default


@register("marvel_rivals", "MR-bot", "Marvel Rivals CN stats query", "1.3.9", "")
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

最近对局、战绩回顾和每日战绩结果会保留 10 分钟；可点击按钮，或回复 /对局 1 ~ /对局 N 查看具体对局。

/战绩回顾 [时间范围] [UID]
查询指定北京时间范围内的统计和全部对局（默认今天）
日期范围格式：/战绩回顾 8月20日-8月21日
也支持：/战绩回顾 8月20日 8月21日
或：/战绩回顾 8月20日到8月21日
跨日期带时间：/战绩回顾 2026-08-15 20:00 2026-08-16 02:00
时间窗口中的击败、死亡、助攻、最后一击、伤害、治疗和承伤按玩家实际游戏时间统一折算为每10分钟；旧接口缺少 playTime 时使用兼容场均口径。

/每日战绩 [日期] [UID]
查询指定日期全天战绩（兼容 /今日战绩）

/我的英雄 <名称> [UID] [赛季]
查询指定英雄的生涯或单赛季综合分析（兼容 /英雄数据、/英雄）

/对局详情 <matchUid|N>
查询对局详情（兼容 /对局 N；N 来自最近或战绩回顾列表）

/对局 <N>
查看当前最近对局或战绩回顾列表中的第 N 场

/卡片测试
测试 QQ 卡片能力

/英雄环境 [段位] [赛季]
查询全局英雄环境总览（默认全段位；不接受排序指标；默认生成图片）

/英雄排行 <胜率|选取率|Ban率|场次> [职责] [段位] [赛季] [范围]
按指标查询英雄排行；支持职责筛选、分职责榜、前 N、区间和最后 N（默认生成图片）

英雄名称支持常用别称，例如：杰夫→陆行鲨杰夫，雷神→索尔

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
查看生涯或单赛季英雄池结构、职责覆盖和核心英雄质量

/我的绝活 [UID] [赛季]
按生涯或指定赛季分析真正擅长的英雄，默认展示 Top 5

/我的绝症 [UID] [赛季]
按生涯或指定赛季分析使用量较高但相对表现偏低的英雄 Top 10
"""

    def __init__(self, context: Context, config=None):
        if hasattr(super(), "__init__"):
            super().__init__(context)
        configured = dict(config or {})
        env_config = {key: value for key, value in os.environ.items() if key.startswith("MRCN_")}
        env_config.update(configured)
        self.source = CNDataSource(env=env_config)
        signature_batch_size = _safe_int_config(env_config, "MRCN_SIGNATURE_HERO_BATCH_SIZE", 32)
        signature_concurrency = _safe_int_config(env_config, "MRCN_SIGNATURE_MAX_CONCURRENCY", 4)
        self.service = RivalsService(
            self.source,
            _safe_float_config(env_config, "MRCN_CACHE_SECONDS", 60),
            hero_batch_size=signature_batch_size,
            hero_max_concurrency=signature_concurrency,
            max_inflight_requests=_safe_int_config(env_config, "MRCN_MAX_INFLIGHT_REQUESTS", 8),
            match_detail_cache_seconds=_safe_float_config(
                env_config, "MRCN_MATCH_DETAIL_CACHE_SECONDS", 86400, minimum=0
            ),
        )
        self.match_history = MatchHistoryService(self.service)
        self.qq_card_sender = QQOfficialCardSender()
        self.message_sender = SenderRouter(OneBotSender())
        self.image_renderer = MatchImageRenderer(
            self.html_render,
            max_concurrent_renders=_safe_int_config(env_config, "MRCN_RENDER_MAX_CONCURRENCY", 2),
            max_retries=_safe_int_config(env_config, "MRCN_RENDER_RETRY_COUNT", 1, minimum=0),
            queue_timeout_seconds=_safe_float_config(
                env_config, "MRCN_RENDER_QUEUE_TIMEOUT_SECONDS", 15, minimum=0.1
            ),
            logger=logger,
        )
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
        self.interaction_sessions = InteractionSessionStore(
            _safe_float_config(env_config, "MRCN_INTERACTION_SESSION_SECONDS", 600, minimum=1)
        )
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
                    request_semaphore=self.service.request_semaphore,
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
        self.player_career_analysis_service = PlayerCareerAnalysisService(
            self.service,
            self.meta_service,
            cache_root=plugin_data_root,
            hero_batch_size=signature_batch_size,
            max_concurrency=signature_concurrency,
            season_policy=(
                env_config.get("MRCN_SIGNATURE_SEASON_POLICY", "independent")
                if str(env_config.get("MRCN_SIGNATURE_SEASON_POLICY", "independent")).lower()
                in {"independent", "cumulative"}
                else "independent"
            ),
            result_cache_seconds=_safe_float_config(env_config, "MRCN_SIGNATURE_RESULT_CACHE_SECONDS", 900),
            historical_cache_seconds=_safe_float_config(env_config, "MRCN_SIGNATURE_HISTORY_CACHE_SECONDS", 7 * 86400),
            current_cache_seconds=_safe_float_config(env_config, "MRCN_SIGNATURE_CURRENT_CACHE_SECONDS", 1800),
            rating_version=(
                str(env_config.get("MRCN_RATING_VERSION", "shadow")).lower()
                if str(env_config.get("MRCN_RATING_VERSION", "shadow")).lower() in {"v1", "shadow", "v2"}
                else "shadow"
            ),
            specialization_min_confidence=_safe_float_config(
                env_config, "MRCN_RATING_SPECIALIZATION_MIN_CONFIDENCE", 0.55
            ),
            specialization_min_experience=_safe_float_config(
                env_config, "MRCN_RATING_SPECIALIZATION_MIN_EXPERIENCE", 20.0
            ),
        )
        # Keep the old attribute for integrations that still import the
        # specialty facade; all three commands share this analysis engine.
        self.player_signature_service = self.player_career_analysis_service

    def _qq_id(self, event: AstrMessageEvent) -> str:
        return str(event.get_sender_id())

    @staticmethod
    def _group_id(event: AstrMessageEvent) -> str:
        getter = getattr(event, "get_group_id", None)
        if callable(getter):
            try:
                value = getter()
                if value not in (None, ""):
                    return str(value)
            except Exception:
                pass
        message_obj = getattr(event, "message_obj", None)
        raw = getattr(message_obj, "raw_message", None)
        for source in (raw, message_obj, event):
            for name in ("group_id", "group_openid", "groupId"):
                value = source.get(name) if isinstance(source, Mapping) else getattr(source, name, None)
                if value not in (None, ""):
                    return str(value)
        return ""

    def _image_result(self, event: AstrMessageEvent, image_url: str):
        sender = getattr(self, "message_sender", None)
        if sender is None:
            return event.image_result(image_url)
        return sender.send_image_with_mention(event, image_url)

    @staticmethod
    def _render_failure(command: str, context: str | None = None) -> str:
        suffix = f"（{context}）" if context else ""
        return f"{command}：Mrrrrrrr！图片生成失败了，请稍后再试。{suffix}"

    @staticmethod
    def _usage_error(reason: str, usage: str) -> str:
        from_text = f"原因：{reason}"
        return (
            "Mrrrrrrr！（杰夫不知道你在说什么，请检查命令是否正确）\n\n"
            f"{from_text}\n用法：{usage}"
        )

    async def terminate(self):
        """Release HTTP connection pools when AstrBot unloads the plugin."""

        for source in (self.source, self.meta_source):
            close = getattr(source, "aclose", None)
            if callable(close):
                await close()

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

    def _selection_session_minutes(self) -> int:
        ttl_seconds = getattr(getattr(self, "interaction_sessions", None), "ttl_seconds", 600)
        try:
            return max(1, int((float(ttl_seconds) + 59) // 60))
        except (TypeError, ValueError):
            return 10

    def _match_window_selection_prompt(self, report) -> str:
        total = len(getattr(report, "matches", ()) or ())
        minutes = self._selection_session_minutes()
        if not total:
            return f"{report.window.label}暂无可供选择的对局。"
        return (
            f"{report.window.label}共 {total} 场对局。"
            f"请在 {minutes} 分钟内回复 /对局 1 ~ /对局 {total} 查看具体对局。"
        )

    @staticmethod
    def _uid_and_season(uid: str, season: str) -> tuple[str, str]:
        uid, season = uid.strip(), season.strip()
        if uid.lower().startswith("s") and not season:
            return "", uid
        return uid, season

    @staticmethod
    def _analysis_scope(season: str | None) -> AnalysisScope:
        if not season:
            return AnalysisScope.career()
        return AnalysisScope.season(parse_season_name(season))

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
                yield event.plain_result(self._render_failure("查询", getattr(stats.profile, "name", None)))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(self._render_failure("查询", getattr(stats.profile, "name", None)))
            else:
                yield self._image_result(event, image_url)
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
            yield self._image_result(event, image_url)

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
            sessions = getattr(self, "interaction_sessions", None)
            if sessions is not None:
                match_uids = [
                    match_uid
                    for match_uid in (self._selection_match_uid(item) for item in matches[:10])
                    if match_uid
                ]
                sessions.set_recent(self._qq_id(event), self._group_id(event), match_uids)
            try:
                image_url = await self.image_renderer.recent(uid, season_code, matches)
            except Exception as exc:
                if logger:
                    logger.warning(f"最近对局图片渲染失败 command=最近对局 uid={uid} render_type=recent error={exc}")
                yield event.plain_result(self._render_failure("最近对局"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_card(event, build_recent_card, uid, season_code, matches, image_url=image_url):
                    yield event.plain_result(format_matches(matches, season_code))
            else:
                yield self._image_result(event, image_url)
                if self._group_id(event):
                    yield event.plain_result(f"回复 /对局 1 ~ /对局 {len(matches[:10])} 查看详情")
        except DataSourceError as exc:
            yield event.plain_result(f"查询失败：{exc}")

    @filter.command("最近")
    async def recent_legacy(self, event: AstrMessageEvent, uid: str = "", season: str = ""):
        """兼容旧版 /最近 指令。"""
        async for result in self.recent(event, uid, season):
            yield result

    async def _match_window_results(self, event: AstrMessageEvent, args, command_name: str):
        try:
            uid = args.uid or self._bound_uid(event)
        except BindingStoreError as exc:
            yield event.plain_result(str(exc))
            return
        if not uid:
            yield event.plain_result("请提供 UID，或先使用 /绑定漫威 <UID>")
            return
        try:
            history = getattr(self, "match_history", None)
            window_loader = getattr(history, "build_match_window_report", None) if history is not None else None
            if not callable(window_loader):
                window_loader = getattr(self.service, "get_match_window_report", None)
            if callable(window_loader):
                report = await window_loader(uid, args.window)
            else:
                # Compatibility for integrations that still expose only the
                # previous daily facade while upgrading the plugin shell.
                report = await self.service.get_daily_report(uid, args.window.start_at.date())
            renderer = getattr(self.image_renderer, "match_window", None)
            if callable(renderer):
                image_urls = await renderer(report)
            else:
                image_urls = [await self.image_renderer.daily(report)]
            if not image_urls:
                raise RuntimeError("未生成战绩图片")
            sessions = getattr(self, "interaction_sessions", None)
            if sessions is not None:
                sessions.set_window(
                    self._qq_id(event),
                    self._group_id(event),
                    [match.match_uid for match in report.matches],
                    report.window.label,
                )
            if self.qq_card_sender.supports(event):
                for image_url in image_urls:
                    if not await self._send_image(event, image_url):
                        yield event.plain_result(
                            format_match_window(report) + "\n\n" + self._match_window_selection_prompt(report)
                        )
                        return
                if not await self._send_card(
                    event,
                    build_match_window_card,
                    report.window.label,
                    report.matches,
                    self._selection_session_minutes(),
                ):
                    yield event.plain_result(self._match_window_selection_prompt(report))
            else:
                for image_url in image_urls:
                    yield self._image_result(event, image_url)
                yield event.plain_result(self._match_window_selection_prompt(report))
        except DataSourceError as exc:
            yield event.plain_result(f"查询失败：{exc}")
        except Exception as exc:
            if logger:
                logger.warning(f"{command_name}图片或查询失败 command={command_name} error={exc}")
            yield event.plain_result(self._render_failure(command_name))

    @filter.command("战绩回顾")
    async def match_window(
        self,
        event: AstrMessageEvent,
        arg1: str = "",
        arg2: str = "",
        arg3: str = "",
        arg4: str = "",
        arg5: str = "",
    ):
        """查询指定北京时间时间范围内的统计和全部对局。"""

        try:
            args = parse_match_window_command_args(arg1, arg2, arg3, arg4, arg5)
        except MatchWindowCommandUsageError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/战绩回顾 [时间范围] [UID]"))
            return
        async for result in self._match_window_results(event, args, "战绩回顾"):
            yield result

    @filter.command("每日战绩", alias={"今日战绩"})
    async def daily_stats(
        self,
        event: AstrMessageEvent,
        arg1: str = "",
        arg2: str = "",
        arg3: str = "",
        arg4: str = "",
        arg5: str = "",
    ):
        """查询指定北京时间日期全天战绩，是战绩回顾的快捷入口。"""

        try:
            args = parse_match_window_command_args(arg1, arg2, arg3, arg4, arg5)
        except MatchWindowCommandUsageError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/每日战绩 [日期] [UID]"))
            return
        daily_tokens = [str(value).strip() for value in (arg1, arg2, arg3, arg4, arg5) if str(value).strip()]
        if len(daily_tokens) > 2 or any(
            ":" in token or token.startswith("最近") or token == "本周"
            for token in daily_tokens
        ):
            yield event.plain_result(self._usage_error("每日战绩只接受日期和 UID；需要具体时段请使用 /战绩回顾", "/每日战绩 [日期] [UID]"))
            return
        async for result in self._match_window_results(event, args, "每日战绩"):
            yield result

    @filter.command("我的英雄", alias={"英雄数据", "英雄"})
    async def hero(self, event: AstrMessageEvent, hero_name: str, uid: str = "", season: str = ""):
        """使用中文英雄名称查询生涯或指定赛季的个人英雄分析。"""
        analysis_service = self._analysis_service()
        uid, season = self._uid_and_season(uid, season)
        try:
            uid = uid or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请提供 UID，或先绑定 UID")
                return
            if callable(getattr(analysis_service, "get_hero_analysis", None)):
                analysis_args = parse_player_analysis_args(uid, season)
                resolved_uid = analysis_args.uid or uid
                resolved_scope = self._analysis_scope(analysis_args.season)
                hero_analysis = await analysis_service.get_hero_analysis(
                    resolved_uid, hero_name, resolved_scope
                )
                analysis_profile = await analysis_service.get_analysis(resolved_uid, resolved_scope)
                fallback = format_player_hero_analysis(analysis_profile, hero_analysis)
                try:
                    image_url = await self.image_renderer.player_hero_analysis(
                        analysis_profile, hero_analysis
                    )
                except Exception as exc:
                    if logger:
                        logger.warning(f"我的英雄分析图片渲染失败 uid={resolved_uid} error={exc}")
                    yield event.plain_result(fallback)
                    return
                if self.qq_card_sender.supports(event):
                    if not await self._send_image(event, image_url):
                        yield event.plain_result(fallback)
                else:
                    yield self._image_result(event, image_url)
                return
            result = await self.service.get_hero_stats(uid, hero_name, season or None)
            try:
                image_url = await self.image_renderer.hero(result)
            except Exception as exc:
                if logger:
                    logger.warning(f"英雄数据图片渲染失败 command=我的英雄 uid={uid} render_type=hero error={exc}")
                yield event.plain_result(self._render_failure("我的英雄"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(format_hero_result(result))
            else:
                yield self._image_result(event, image_url)
        except (DataSourceError, BindingStoreError, PlayerMetaQueryError, ValueError) as exc:
            yield event.plain_result(f"查询失败：{exc}")

    def _resolve_match_selection(self, event: AstrMessageEvent, value: str) -> str:
        candidate = str(value).strip()
        if not candidate.isdigit():
            return candidate
        index = int(candidate)
        sessions = getattr(self, "interaction_sessions", None)
        if sessions is None:
            return candidate
        getter = getattr(sessions, "get", None) or getattr(sessions, "get_recent", None)
        session = getter(self._qq_id(event), self._group_id(event)) if callable(getter) else None
        if session is None:
            raise CommandUsageError("对局列表选择已过期，请重新使用 /最近对局或 /战绩回顾")
        session_label = getattr(session, "label", "最近对局")
        if not 1 <= index <= len(session.match_uids):
            raise CommandUsageError(f"{session_label}只有 {len(session.match_uids)} 场，无法选择第 {index} 场")
        return session.match_uids[index - 1]

    @staticmethod
    def _selection_match_uid(item: object) -> str:
        typed_uid = getattr(item, "match_uid", None)
        if typed_uid not in (None, ""):
            return str(typed_uid)
        getter = getattr(item, "get", None)
        if callable(getter):
            match_uid = getter("matchUid", getter("matchUID", getter("id", "")))
            if match_uid not in (None, ""):
                return str(match_uid)
        return ""

    @filter.command("对局详情", alias={"对局"})
    async def match_detail(self, event: AstrMessageEvent, match_uid: str):
        """使用 matchUid 查询详情，支持纯 ID 或 matchUid=... 格式。"""
        try:
            sender_id = self._qq_id(event)
        except Exception:
            sender_id = "unknown"
        group_id = self._group_id(event)
        input_value = str(match_uid).strip()
        if logger:
            logger.info(
                f"对局详情命令进入 sender_id={sender_id} group_id={group_id} input={input_value}"
            )
        try:
            resolve_started = perf_counter()
            match_uid = self._resolve_match_selection(event, match_uid)
            if logger:
                logger.info(
                    f"对局详情选择解析完成 sender_id={sender_id} group_id={group_id} "
                    f"input={input_value} resolved_match_uid={match_uid} "
                    f"resolve_ms={(perf_counter() - resolve_started) * 1000:.1f}"
                )
            request_started = perf_counter()
            payload = await self.service.get_match_detail(match_uid)
            if logger:
                logger.info(
                    f"对局详情数据请求完成 sender_id={sender_id} group_id={group_id} "
                    f"resolved_match_uid={match_uid} request_ms={(perf_counter() - request_started) * 1000:.1f}"
                )
            try:
                image_url = await self.image_renderer.detail(payload)
            except Exception as exc:
                if logger:
                    logger.warning(
                        f"对局详情图片渲染失败 sender_id={sender_id} group_id={group_id} "
                        f"resolved_match_uid={match_uid} error={type(exc).__name__}:{exc}"
                    )
                yield event.plain_result(self._render_failure("对局详情", f"matchUid：{match_uid}"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(format_match_detail(payload))
            else:
                yield self._image_result(event, image_url)
        except CommandUsageError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/对局 <matchUid|N>"))
        except (DataSourceError, BindingStoreError) as exc:
            yield event.plain_result(f"查询失败：{exc}")

    def _meta_unavailable(self) -> str:
        return "当前未启用英雄环境功能"

    def _analysis_service(self):
        """Return the shared analysis service, with old test/integration fallback."""

        return (
            getattr(self, "player_career_analysis_service", None)
            or getattr(self, "player_signature_service", None)
        )

    def _meta_source_failure(self, error: MetaDataSourceError) -> str:
        if logger:
            logger.warning(f"Meta 数据源错误：{type(error).__name__}")
        return "查询失败：英雄环境数据源暂时不可用，请稍后重试"

    async def _render_meta_result(self, event, model, fallback: str, renderer) -> object | None:
        try:
            image_url = await renderer(model)
        except Exception as exc:
            if logger:
                logger.warning(f"Meta 图片渲染失败 render_type={type(model).__name__} error={exc}")
            return event.plain_result(self._render_failure("英雄环境"))
        if self.qq_card_sender.supports(event):
            if not await self._send_image(event, image_url):
                return event.plain_result(fallback)
            return None
        return self._image_result(event, image_url)

    @filter.command("英雄环境")
    async def hero_meta(self, event: AstrMessageEvent, arg1: str = "", arg2: str = "", arg3: str = "", arg4: str = ""):
        """查询指定赛季和段位的全局英雄环境，不接受排序指标。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_meta_command_args(arg1, arg2, arg3, arg4, allow_sort=False)
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
                yield event.plain_result(self._render_failure("当前英雄环境"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield self._image_result(event, image_url)
        except CommandUsageError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄环境 [段位] [赛季]"))
        except ValueError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄环境 [段位] [赛季]"))
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("英雄排行")
    async def hero_meta_rank(self, event: AstrMessageEvent, arg1: str = "", arg2: str = "", arg3: str = "", arg4: str = "", arg5: str = ""):
        """按一个胜率、选取率、Ban率或场次指标查询英雄排行，不接受英雄名称。"""
        if self.meta_service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_meta_command_args(
                arg1,
                arg2,
                arg3,
                arg4,
                arg5,
                require_sort=True,
            )
            board = await self.meta_service.get_hero_meta_board(
                season=args.season,
                rank=args.rank,
                sort_by=args.sort_by,
                role=args.role,
                ranking_range=args.ranking_range,
                group_by_role=args.group_by_role,
                limit=10,
            )
            fallback = format_hero_meta_board(board)
            try:
                image_url = await self.image_renderer.meta_board(board)
            except Exception as exc:
                if logger:
                    logger.warning(f"英雄排行图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(self._render_failure("英雄排行"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield self._image_result(event, image_url)
        except CommandUsageError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄排行 <胜率|选取率|Ban率|场次> [职责] [段位] [赛季] [范围]"))
        except ValueError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄排行 <胜率|选取率|Ban率|场次> [职责] [段位] [赛季] [范围]"))
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
                yield event.plain_result(self._render_failure("英雄统计"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield self._image_result(event, image_url)
        except CommandUsageError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄统计 <英雄名称> [段位] [赛季]"))
        except ValueError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄统计 <英雄名称> [段位] [赛季]"))
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
                yield event.plain_result(self._render_failure("英雄分段"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield self._image_result(event, image_url)
        except CommandUsageError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄分段 <英雄名称> [赛季]"))
        except ValueError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄分段 <英雄名称> [赛季]"))
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
                yield event.plain_result(self._render_failure("英雄对比"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield self._image_result(event, image_url)
        except CommandUsageError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄对比 <英雄1> <英雄2> [段位] [赛季]"))
        except ValueError as exc:
            yield event.plain_result(self._usage_error(str(exc), "/英雄对比 <英雄1> <英雄2> [段位] [赛季]"))
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
                yield event.plain_result(self._render_failure("我的环境"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield self._image_result(event, image_url)
        except (ValueError, DataSourceError) as exc:
            yield event.plain_result(f"查询失败：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("我的英雄池")
    async def my_hero_pool(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """展示生涯或指定赛季的个人英雄池结构与核心质量。"""
        service = self._analysis_service()
        if service is None:
            yield event.plain_result("当前个人英雄分析功能不可用")
            return
        try:
            args = parse_player_analysis_args(arg1, arg2)
            uid = args.uid or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请先使用 /绑定账号 <UID>，或直接提供 UID")
                return
            scope = self._analysis_scope(args.season)
            if not callable(getattr(service, "get_hero_pool_analysis", None)):
                raise PlayerMetaQueryError("个人英雄池分析接口不可用")
            pool = await service.get_hero_pool_analysis(uid, scope)
            fallback = format_player_hero_pool_analysis(pool)
            try:
                image_url = await self.image_renderer.player_hero_pool_analysis(pool)
            except Exception as exc:
                if logger:
                    logger.warning(f"我的英雄池图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(self._render_failure("我的英雄池"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield self._image_result(event, image_url)
        except (ValueError, DataSourceError) as exc:
            yield event.plain_result(f"查询失败：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("我的绝活")
    async def my_signature(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """按生涯或指定赛季展示玩家的高表现英雄。"""
        service = self._analysis_service()
        if service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_player_analysis_args(arg1, arg2)
            uid = args.uid or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请先使用 /绑定账号 <UID>，或直接提供 UID")
                return
            if callable(getattr(service, "get_analysis", None)):
                scope = self._analysis_scope(args.season)
                profile = await service.get_analysis(uid, scope)
            elif args.season:
                profile = await service.get_player_signature(uid, top_n=5, season=args.season)
            else:
                profile = await service.get_player_signature(uid, top_n=5)
            fallback = format_player_signature(profile)
            try:
                image_url = await self.image_renderer.player_signature(profile)
            except Exception as exc:
                if logger:
                    logger.warning(f"我的绝活图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(self._render_failure("我的绝活"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield self._image_result(event, image_url)
        except (ValueError, DataSourceError) as exc:
            yield event.plain_result(f"查询失败：{exc}")
        except MetaDataSourceError as exc:
            yield event.plain_result(self._meta_source_failure(exc))

    @filter.command("我的绝症")
    async def my_sickness(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """按生涯或指定赛季展示高使用量的相对弱势英雄。"""
        service = self._analysis_service()
        if service is None:
            yield event.plain_result(self._meta_unavailable())
            return
        try:
            args = parse_player_analysis_args(arg1, arg2)
            uid = args.uid or self._bound_uid(event)
            if not uid:
                yield event.plain_result("请先使用 /绑定账号 <UID>，或直接提供 UID")
                return
            if callable(getattr(service, "get_analysis", None)):
                scope = self._analysis_scope(args.season)
                profile = await service.get_analysis(uid, scope)
            elif args.season:
                profile = await service.get_player_signature(uid, top_n=5, season=args.season)
            else:
                profile = await service.get_player_signature(uid, top_n=5)
            fallback = format_player_sickness(profile)
            try:
                image_url = await self.image_renderer.player_sickness(profile)
            except Exception as exc:
                if logger:
                    logger.warning(f"我的绝症图片渲染失败，回退普通文本：{exc}")
                yield event.plain_result(self._render_failure("我的绝症"))
                return
            if self.qq_card_sender.supports(event):
                if not await self._send_image(event, image_url):
                    yield event.plain_result(fallback)
            else:
                yield self._image_result(event, image_url)
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
