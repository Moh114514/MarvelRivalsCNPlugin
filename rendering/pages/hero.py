"""Hero statistics page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.models import HeroQueryResult
    from ...marvel_rivals_bot.hero_names import format_hero_name
    from ...marvel_rivals_bot.services.rivals import format_season_name
except ImportError:
    from marvel_rivals_bot.models import HeroQueryResult
    from marvel_rivals_bot.hero_names import format_hero_name
    from marvel_rivals_bot.services.rivals import format_season_name

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import extract_career, format_number


def build_hero_query_html(result: HeroQueryResult) -> str:
    hero = extract_career(result)
    matches, wins = hero.get("totalMatchCount"), hero.get("totalMatchWinCount")
    win_rate = wins * 100 / matches if isinstance(matches, (int, float)) and matches and isinstance(wins, (int, float)) else None
    overview = metric_grid((
        ("比赛", format_number({"value": matches}, "value")),
        ("胜场", format_number({"value": wins}, "value")),
        ("胜率", f"{format_number({'value': win_rate}, 'value')}%"),
        ("K / D / A", "/".join(format_number(hero, key) for key in ("k", "d", "a"))),
    ))
    details = (
        '<section class="mr-section">'
        + section_title("核心表现", "CAREER METRICS")
        + metric_grid((
            ("英雄伤害", format_number(hero, "totalHeroDamage")),
            ("治疗", format_number(hero, "totalHeroHeal")),
            ("承受伤害", format_number(hero, "totalDamageTaken")),
            ("MVP / SVP", f"{format_number(hero, 'totalMvpTimes')}/{format_number(hero, 'totalSvpTimes')}"),
        ))
        + '</section>'
    ) if hero else empty_state("暂无该英雄的生涯数据")
    title = format_hero_name(result.hero_id, result.hero_name)
    content = (
        page_header(
            "HERO DATA",
            f"UID {result.uid} · 英雄 ID {result.hero_id}",
            format_season_name(result.season),
            title_cn=title,
        )
        + overview
        + details
    )
    return page_shell(content, watermark="HERO DATA")
