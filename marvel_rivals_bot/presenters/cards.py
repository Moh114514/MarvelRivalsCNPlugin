from __future__ import annotations

from typing import Any

from ..hero_names import format_hero_name
from ..models import PlayerStats
from ..services.rivals import format_season_name


def _count(value: int | float | None) -> str:
    return "-" if not isinstance(value, (int, float)) else str(round(value))


def _win_rate(value: float | None) -> str:
    return "-" if not isinstance(value, (int, float)) else f"{value:.1f}%"


def build_player_card(stats: PlayerStats, theme: str = "dark") -> dict[str, Any]:
    """Build an AstrBot-independent view model for the player overview card."""
    profile, summary = stats.profile, stats.summary
    return {
        "theme": theme if theme in {"dark", "light"} else "dark",
        "season": format_season_name(stats.season),
        "player": {
            "name": profile.name,
            "uid": profile.uid,
            "level": str(profile.level) if profile.level is not None else "-",
            "rank": profile.rank_game_season or "暂无段位",
        },
        "summary": {
            "matches": _count(summary.matches),
            "wins": _count(summary.wins),
            "win_rate": _win_rate(summary.win_rate),
            "kills": _count(summary.kills),
            "deaths": _count(summary.deaths),
            "assists": _count(summary.assists),
        },
        "heroes": [
            {
                "position": f"{index:02d}",
                "name": format_hero_name(hero.hero_id, hero.hero_name),
                "matches": _count(hero.matches),
                "wins": _count(hero.wins),
                "kills": _count(hero.kills),
            }
            for index, hero in enumerate(stats.heroes[:5], 1)
        ],
    }
