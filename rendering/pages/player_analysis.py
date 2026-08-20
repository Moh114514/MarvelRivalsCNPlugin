"""Single-hero view for the shared player career analysis."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.analytics.models import CareerHeroSignature, PlayerSignatureProfile
except ImportError:
    from marvel_rivals_bot.analytics.models import CareerHeroSignature, PlayerSignatureProfile

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import escape_text


def _value(value) -> str:
    return "—" if value is None else f"{value:,}" if isinstance(value, int) else f"{value:.1f}"


def _percent(value) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _delta(value) -> str:
    return "—" if value is None else f"{value:+.1f}pp"


def _hours(value) -> str:
    return "—" if value is None else f"{value / 3600:.1f} 小时"


def _mode_block(title: str, stats) -> str:
    if stats is None or stats.matches is None:
        return empty_state(f"{title}暂无数据")
    matches = stats.matches
    average = lambda name: "—" if getattr(stats, name, None) is None or not matches else f"{getattr(stats, name) / matches:.1f}"
    return (
        '<section class="mr-section">'
        + section_title(title, "MODE DETAILS")
        + metric_grid((
            ("场次", _value(stats.matches)),
            ("胜率", _percent(stats.win_rate)),
            ("击败", _value(stats.kills)),
            ("最后一击", _value(stats.final_hits)),
            ("死亡", _value(stats.deaths)),
            ("助攻", _value(stats.assists)),
            ("场均伤害", average("hero_damage")),
            ("场均治疗", average("heal")),
            ("场均承伤", average("damage_taken")),
            ("游戏时长", _hours(stats.play_time)),
            ("MVP", _value(stats.mvp)),
            ("SVP", _value(stats.svp)),
        ))
        + '</section>'
    )


def build_player_hero_analysis_html(
    profile: PlayerSignatureProfile,
    hero: CareerHeroSignature,
) -> str:
    scope_label = "生涯" if profile.scope.kind == "career" else profile.scope.season_code
    title = f"{hero.hero_name} · {scope_label}分析"
    if hero.signature_score > 0:
        conclusion = "强势绝活"
        description = "长期表现明显高于自身及同期环境。"
    elif hero.sickness_score > 0:
        conclusion = "高使用量相对弱势"
        description = "使用量较高，但相对同期环境和个人同模式基准表现偏低。"
    else:
        conclusion = "潜力 / 常用英雄"
        description = "当前数据不足以归入强势绝活或高使用量弱势。"
    content = page_header(
        "MY HERO ANALYSIS",
        description,
        title,
        title_cn=title,
        meta_items=(
            ("综合表现", f"{hero.performance_index:+.1f}"),
            ("使用指数", f"{hero.play_index:.1f}"),
            ("可信度", hero.confidence),
        ),
    )
    content += '<section class="mr-section">' + section_title(conclusion, "CONCLUSION")
    content += metric_grid((
        ("绝活指数", f"{hero.signature_score:.1f}"),
        ("绝症指数", f"{hero.sickness_score:.1f}"),
        ("总场次", _value(hero.total_matches)),
        ("竞技场次", _value(hero.competitive_matches)),
        ("快速场次", _value(hero.quick_matches)),
        ("活跃赛季", _value(hero.active_seasons)),
    )) + '</section>'
    content += '<section class="mr-section">' + section_title("竞技环境比较", "ENVIRONMENT")
    content += metric_grid((
        ("个人竞技胜率", _percent(hero.actual_win_rate)),
        ("同期同段位 Meta", _percent(hero.expected_meta_win_rate)),
        ("Meta 表现", _delta(
            hero.adjusted_meta_delta
            if hero.adjusted_meta_delta is not None else hero.adjusted_delta
        )),
        ("个人竞技相对表现", _delta(hero.personal_competitive_delta)),
        ("个人快速相对表现", _delta(hero.personal_quick_delta)),
        ("Meta 覆盖", f"{hero.meta_coverage:.0f}%"),
    )) + '</section>'
    content += _mode_block("竞技详细数据", hero.competitive_stats)
    content += _mode_block("快速详细数据", hero.quick_stats)
    return page_shell(content, watermark="MY HERO ANALYSIS")


__all__ = ["build_player_hero_analysis_html"]
