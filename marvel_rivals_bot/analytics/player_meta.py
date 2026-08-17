"""Composite analytics joining CN player data with global Meta data."""

from __future__ import annotations

import re
from typing import Any

from ..models import HeroStat, PlayerHeroStats, PlayerStats
from ..reference.ranks import CN_RANK_LEVEL_MAP, meta_rank_from_cn_level
from .models import PlayerHeroMetaComparison, PlayerMetaProfile


class PlayerMetaQueryError(ValueError):
    """A user-safe error raised while resolving player Meta context."""


DEFAULT_SIGNATURE_MIN_MATCHES = 20
DEFAULT_SIGNATURE_MIN_RANKED_MATCHES = 10


class PlayerMetaService:
    """Combine existing player and Meta services without coupling their sources."""

    def __init__(self, rivals_service, meta_service):
        self.rivals_service = rivals_service
        self.meta_service = meta_service

    async def get_player_meta_profile(
        self,
        uid: str,
        *,
        season: str | None = None,
        hero_limit: int = 10,
        minimum_matches: int = DEFAULT_SIGNATURE_MIN_MATCHES,
        minimum_ranked_matches: int = DEFAULT_SIGNATURE_MIN_RANKED_MATCHES,
        include_environment: bool = False,
        include_hero_pool: bool = False,
        include_signature: bool = False,
    ) -> PlayerMetaProfile:
        if self.meta_service is None:
            raise PlayerMetaQueryError("当前未启用英雄环境功能")
        if include_hero_pool or include_signature:
            stats = await self.rivals_service.get_player_stats(uid, season)
        else:
            profile_loader = getattr(self.rivals_service, "get_player_profile", None)
            if callable(profile_loader):
                profile = await profile_loader(uid, season)
                season_code_loader = getattr(self.rivals_service, "season_code", None)
                season_code = season_code_loader(season) if callable(season_code_loader) else str(season or "")
                stats = PlayerStats(profile=profile, season=season_code)
            else:
                # Compatibility fallback for lightweight integrations written
                # before the profile-only source method was introduced.
                stats = await self.rivals_service.get_player_stats(uid, season)
        rank_level, cn_rank_label, meta_rank_code = self._resolve_rank(stats)
        board = await self.meta_service.get_hero_meta_board(
            season=stats.season,
            rank=meta_rank_code,
            sort_by="matches",
            limit=None,
        )
        environment = None
        if include_environment:
            environment = await self.meta_service.get_hero_meta_overview(
                season=stats.season,
                rank=meta_rank_code,
                limit=5,
            )
        hero_pool = ()
        if include_hero_pool or include_signature:
            hero_pool = tuple(
                self._compare_heroes(stats.heroes, board.heroes, hero_limit)
            )
        signature = ()
        if include_signature:
            # The competitive gate remains a product rule; the total-match
            # threshold may be overridden by the numeric command argument.
            threshold = self._minimum_matches(minimum_matches)
            ranked_threshold = DEFAULT_SIGNATURE_MIN_RANKED_MATCHES
            signature = tuple(
                item
                for item in hero_pool
                if (
                    item.total_matches is not None
                    and item.ranked_matches is not None
                    and item.total_matches >= threshold
                    and item.ranked_matches >= ranked_threshold
                    and item.ranked_win_rate is not None
                    and item.meta_win_rate is not None
                    and item.ranked_win_rate > item.meta_win_rate
                )
            )
            signature = tuple(
                sorted(
                    signature,
                    key=lambda item: (
                        item.competitive_win_rate_delta is not None,
                        (
                            item.competitive_win_rate_delta
                            if item.competitive_win_rate_delta is not None
                            else float("-inf")
                        ),
                        item.competitive_matches or 0,
                        item.total_matches,
                    ),
                    reverse=True,
                )
            )
        if include_hero_pool and not hero_pool:
            raise PlayerMetaQueryError(self._hero_data_error(stats))
        if include_signature and not signature:
            if not self._has_comparable_hero_data(stats):
                raise PlayerMetaQueryError(self._hero_data_error(stats))
            raise PlayerMetaQueryError("没有同时满足总场次、竞技场次和同段位 Meta 胜率要求的英雄")
        return PlayerMetaProfile(
            uid=stats.profile.uid,
            player_name=stats.profile.name,
            cn_rank_label=cn_rank_label,
            cn_rank_level=rank_level,
            meta_rank_code=meta_rank_code,
            meta_rank_label=board.rank_label,
            season_code=board.season_code,
            season_label=board.season_label,
            source=board.source,
            source_timestamp=board.source_timestamp,
            fetched_at=board.fetched_at,
            stale=board.stale,
            environment=environment,
            hero_pool=hero_pool,
            signature_heroes=signature,
            minimum_matches=threshold if include_signature else self._minimum_matches(minimum_matches),
            minimum_ranked_matches=DEFAULT_SIGNATURE_MIN_RANKED_MATCHES if include_signature else self._minimum_matches(minimum_ranked_matches),
        )

    async def get_player_environment(self, uid: str, *, season: str | None = None) -> PlayerMetaProfile:
        return await self.get_player_meta_profile(uid, season=season, include_environment=True)

    async def get_player_hero_pool(
        self,
        uid: str,
        *,
        season: str | None = None,
        hero_limit: int = 10,
    ) -> PlayerMetaProfile:
        return await self.get_player_meta_profile(
            uid,
            season=season,
            hero_limit=hero_limit,
            include_hero_pool=True,
        )

    async def get_player_signature(
        self,
        uid: str,
        *,
        season: str | None = None,
        minimum_matches: int = DEFAULT_SIGNATURE_MIN_MATCHES,
        minimum_ranked_matches: int = DEFAULT_SIGNATURE_MIN_RANKED_MATCHES,
        hero_limit: int = 10,
    ) -> PlayerMetaProfile:
        return await self.get_player_meta_profile(
            uid,
            season=season,
            hero_limit=hero_limit,
            minimum_matches=minimum_matches,
            minimum_ranked_matches=minimum_ranked_matches,
            include_signature=True,
        )

    @staticmethod
    def _minimum_matches(value: Any) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise PlayerMetaQueryError("最低场次必须是正整数") from exc
        if value < 1:
            raise PlayerMetaQueryError("最低场次必须是正整数")
        return value

    @staticmethod
    def _hero_total_matches(hero: PlayerHeroStats | HeroStat) -> int | None:
        value = getattr(hero, "total_matches", None)
        if value is None:
            value = getattr(hero, "matches", None)
        return int(value) if value is not None else None

    @classmethod
    def _has_comparable_hero_data(cls, stats: PlayerStats) -> bool:
        return any(
            (matches := cls._hero_total_matches(hero)) is not None and matches > 0
            for hero in stats.heroes
        )

    @classmethod
    def _hero_data_error(cls, stats: PlayerStats) -> str:
        if not stats.heroes:
            return "本赛季没有英雄记录"
        if not any(cls._hero_total_matches(hero) is not None for hero in stats.heroes):
            return "常用英雄已获取，但英雄详细数据获取失败"
        if not cls._has_comparable_hero_data(stats):
            return "本赛季没有可用于比较的英雄场次"
        return "个人英雄数据存在，但没有可与 RivalsMeta 匹配的英雄"

    @staticmethod
    def _resolve_rank(stats: PlayerStats) -> tuple[int, str, str]:
        profile = stats.profile
        rank_level = getattr(profile, "rank_level", None)
        if rank_level is None:
            rank_level = PlayerMetaService._rank_level_from_text(profile.rank_game_season)
        meta_rank_code = meta_rank_from_cn_level(rank_level)
        if rank_level is None or meta_rank_code is None:
            raise PlayerMetaQueryError("无法识别绑定账号的当前段位，暂时不能匹配同段位环境")
        cn_rank_label = profile.rank_game_season or CN_RANK_LEVEL_MAP.get(
            int(rank_level), f"等级 {int(rank_level)}"
        )
        return int(rank_level), cn_rank_label, meta_rank_code

    @staticmethod
    def _rank_level_from_text(value: Any) -> int | None:
        text = str(value or "").strip()
        if not text:
            return None
        for level, label in CN_RANK_LEVEL_MAP.items():
            base = re.sub(r"(?:[1-3]|[ⅠⅡⅢIV]+)$", "", label)
            if text.startswith(label) or text.startswith(base):
                return level
        if text.startswith("白金"):
            return 10
        return None

    @staticmethod
    def _compare_heroes(
        heroes: list[PlayerHeroStats | HeroStat],
        meta_results,
        limit: int,
    ) -> list[PlayerHeroMetaComparison]:
        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError) as exc:
            raise PlayerMetaQueryError("英雄池数量必须是正整数") from exc
        by_id = {str(result.hero_id): result for result in meta_results}
        scoped = [(hero, PlayerMetaService._hero_scopes(hero)) for hero in heroes]
        selected = sorted(
            (
                (hero, values)
                for hero, values in scoped
                if values[0] is not None and values[0] > 0
            ),
            key=lambda item: (item[1][0], str(item[0].hero_id)),
            reverse=True,
        )[:limit]
        rows: list[PlayerHeroMetaComparison] = []
        for hero, (total_matches, quick_matches, ranked_matches, ranked_wins, ranked_rate) in selected:
            meta = by_id.get(str(hero.hero_id))
            meta_rate = meta.win_rate if meta is not None else None
            delta = ranked_rate - meta_rate if ranked_rate is not None and meta_rate is not None else None
            rows.append(
                PlayerHeroMetaComparison(
                    hero_id=str(hero.hero_id),
                    hero_name=hero.hero_name,
                    total_matches=total_matches,
                    quick_matches=quick_matches,
                    competitive_matches=ranked_matches,
                    competitive_wins=ranked_wins,
                    competitive_win_rate=ranked_rate,
                    competitive_share=(
                        ranked_matches * 100 / total_matches
                        if ranked_matches is not None and total_matches
                        else None
                    ),
                    meta_matches=meta.matches if meta is not None else None,
                    meta_win_rate=meta_rate,
                    meta_pick_rate=meta.pick_rate if meta is not None else None,
                    meta_ban_rate=meta.ban_rate if meta is not None else None,
                    competitive_win_rate_delta=delta,
                )
            )
        return rows

    @staticmethod
    def _hero_scopes(
        hero: PlayerHeroStats | HeroStat,
    ) -> tuple[int | None, int | None, int | None, int | None, float | None]:
        """Return total, quick, ranked, ranked wins, and ranked WR."""

        if isinstance(hero, PlayerHeroStats) or hasattr(hero, "ranked"):
            total_value = getattr(hero, "total_matches", None)
            total_matches = int(total_value) if total_value is not None else None
            quick = getattr(hero, "quick", None)
            ranked = getattr(hero, "competitive", getattr(hero, "ranked", None))
            quick_value = getattr(quick, "matches", None)
            ranked_value = getattr(ranked, "matches", None)
            quick_matches = int(quick_value) if quick_value is not None else None
            ranked_matches = int(ranked_value) if ranked_value is not None else None
            ranked_wins = getattr(ranked, "wins", None)
            ranked_rate = getattr(ranked, "win_rate", None)
            return total_matches, quick_matches, ranked_matches, ranked_wins, ranked_rate

        # Compatibility with callers that still construct the old one-scope
        # HeroStat. Treat that scope as ranked until the caller migrates.
        total_value = getattr(hero, "matches", None)
        total_matches = int(total_value) if total_value is not None else None
        wins = getattr(hero, "wins", None)
        rate = getattr(hero, "win_rate", None)
        if rate is None and total_matches and wins is not None:
            rate = wins * 100 / total_matches
        return total_matches, 0, total_matches, wins, rate


__all__ = [
    "DEFAULT_SIGNATURE_MIN_MATCHES",
    "DEFAULT_SIGNATURE_MIN_RANKED_MATCHES",
    "PlayerMetaQueryError",
    "PlayerMetaService",
]
