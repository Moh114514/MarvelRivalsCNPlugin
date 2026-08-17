"""Composite analytics joining CN player data with global Meta data."""

from __future__ import annotations

import re
from typing import Any

from ..models import HeroStat, PlayerStats
from ..reference.ranks import CN_RANK_LEVEL_MAP, meta_rank_from_cn_level
from .models import PlayerHeroMetaComparison, PlayerMetaProfile


class PlayerMetaQueryError(ValueError):
    """A user-safe error raised while resolving player Meta context."""


DEFAULT_SIGNATURE_MIN_MATCHES = 20


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
        include_environment: bool = False,
        include_hero_pool: bool = False,
        include_signature: bool = False,
    ) -> PlayerMetaProfile:
        if self.meta_service is None:
            raise PlayerMetaQueryError("当前未启用英雄环境功能")
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
            threshold = self._minimum_matches(minimum_matches)
            signature = tuple(
                item
                for item in hero_pool
                if item.personal_matches >= threshold
            )
            signature = tuple(
                sorted(
                    signature,
                    key=lambda item: (
                        item.win_rate_delta is not None,
                        item.win_rate_delta if item.win_rate_delta is not None else float("-inf"),
                        item.personal_matches,
                    ),
                    reverse=True,
                )
            )
        if include_hero_pool and not hero_pool:
            raise PlayerMetaQueryError("没有可用于比较的个人英雄数据")
        if include_signature and not signature:
            raise PlayerMetaQueryError(
                f"没有达到最低 {self._minimum_matches(minimum_matches)} 场的个人英雄数据"
            )
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
            minimum_matches=self._minimum_matches(minimum_matches),
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
        hero_limit: int = 10,
    ) -> PlayerMetaProfile:
        return await self.get_player_meta_profile(
            uid,
            season=season,
            hero_limit=hero_limit,
            minimum_matches=minimum_matches,
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
        heroes: list[HeroStat],
        meta_results,
        limit: int,
    ) -> list[PlayerHeroMetaComparison]:
        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError) as exc:
            raise PlayerMetaQueryError("英雄池数量必须是正整数") from exc
        by_id = {str(result.hero_id): result for result in meta_results}
        selected = sorted(
            (hero for hero in heroes if hero.matches is not None and hero.matches > 0),
            key=lambda hero: (hero.matches or 0, str(hero.hero_id)),
            reverse=True,
        )[:limit]
        rows: list[PlayerHeroMetaComparison] = []
        for hero in selected:
            personal_rate = None
            if hero.matches and hero.wins is not None:
                personal_rate = hero.wins * 100 / hero.matches
            meta = by_id.get(str(hero.hero_id))
            meta_rate = meta.win_rate if meta is not None else None
            delta = personal_rate - meta_rate if personal_rate is not None and meta_rate is not None else None
            rows.append(
                PlayerHeroMetaComparison(
                    hero_id=str(hero.hero_id),
                    hero_name=hero.hero_name,
                    personal_matches=int(hero.matches or 0),
                    personal_wins=hero.wins,
                    personal_win_rate=personal_rate,
                    meta_matches=meta.matches if meta is not None else None,
                    meta_win_rate=meta_rate,
                    meta_pick_rate=meta.pick_rate if meta is not None else None,
                    meta_ban_rate=meta.ban_rate if meta is not None else None,
                    win_rate_delta=delta,
                )
            )
        return rows


__all__ = [
    "DEFAULT_SIGNATURE_MIN_MATCHES",
    "PlayerMetaQueryError",
    "PlayerMetaService",
]
