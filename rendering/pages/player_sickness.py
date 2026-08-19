"""Career sickness page for high-volume heroes with below-Meta performance."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.analytics.models import PlayerSignatureProfile
except ImportError:
    from marvel_rivals_bot.analytics.models import PlayerSignatureProfile

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import escape_text


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}pp"


def _sick_card(index: int, item) -> str:
    return (
        '<article class="mr-sickness-card">'
        f'<div class="mr-sickness-card__index">{index:02d}</div>'
        '<div class="mr-sickness-card__main">'
        f'<div class="mr-sickness-card__name">{escape_text(item.hero_name)}</div>'
        '<div class="mr-sickness-card__stats">'
        f'<span>竞技 {item.comparable_matches:,} 场</span>'
        f'<span>实际胜率 {escape_text(_percent(item.actual_win_rate))}</span>'
        f'<span>同期 Meta {escape_text(_percent(item.expected_meta_win_rate))}</span>'
        '</div>'
        '<div class="mr-sickness-card__detail">'
        f'<span>稳健劣势 {escape_text(_delta(item.adjusted_delta))}</span>'
        f'<span>Meta 覆盖 {item.meta_coverage:.0f}%</span>'
        f'<span>同段位覆盖 {item.rank_specific_coverage:.0f}%</span>'
        f'<span>可信度 {escape_text(item.confidence)}</span>'
        '</div>'
        '</div>'
        '<div class="mr-sickness-card__score">'
        '<span>预计少赢</span>'
        f'<strong>{item.sick_score:.1f} 场</strong>'
        '<small>绝症指数</small>'
        '</div>'
        '</article>'
    )


def _sickness_glossary() -> str:
    entries = (
        ("绝症候选", "只纳入竞技可比较场次至少 20 场、Meta 有效覆盖至少 60%、稳健劣势不高于 -2pp 的常用英雄。"),
        ("绝症指数", "稳健劣势的绝对值 × 可比较竞技场次，可以理解为相对同期环境预计少赢的场次。"),
        ("同期 Meta", "RivalsMeta 的第三方同期环境数据，优先使用玩家历史段位对应的 Meta 大段位。"),
        ("为什么没有凑满 Top 10", "只有达到候选条件的英雄才会进入排名；没有符合条件的英雄时不会用低质量数据强行填充。"),
    )
    cards = "".join(
        f'<article class="mr-sickness-glossary__item">'
        f'<strong>{escape_text(term)}</strong>'
        f'<span>{escape_text(description)}</span>'
        f'</article>'
        for term, description in entries
    )
    return (
        '<section class="mr-section mr-sickness-glossary-section">'
        + section_title("判定说明", "HOW SICKNESS IS SCORED")
        + f'<div class="mr-sickness-glossary">{cards}</div>'
        + '</section>'
    )


def build_player_sickness_html(profile: PlayerSignatureProfile) -> str:
    first = profile.first_season or "未知"
    latest = profile.latest_season or first
    content = page_header(
        "MY SICKNESS",
        "高使用量低胜率分析",
        f"{first} — {latest}",
        title_cn=f"{profile.player_name} 的绝症",
        eyebrow="MY SICKNESS",
        meta_items=(
            ("竞技总场次", f"{profile.competitive_matches:,}"),
            ("候选数量", len(profile.sick_heroes)),
            ("Meta 覆盖", f"{profile.meta_coverage:.0f}%"),
        ),
    )
    if profile.partial:
        content += (
            '<div class="mr-meta-source">'
            '部分历史赛季或 Meta 数据不可用，以下仅展示可确认的绝症候选。'
            '</div>'
        )
    if profile.meta_source_timestamp:
        stale_text = "（部分使用最近缓存）" if profile.meta_stale else ""
        content += (
            '<div class="mr-meta-source">'
            f'{escape_text(f"Meta 来源：{profile.meta_source} · 最新上游时间：{profile.meta_source_timestamp}{stale_text}")}'
            '</div>'
        )
    content += metric_grid((
        ("竞技总场次", f"{profile.competitive_matches:,}"),
        ("绝症候选", len(profile.sick_heroes)),
        ("Meta 覆盖", f"{profile.meta_coverage:.0f}%"),
    ))
    content += '<section class="mr-section mr-sickness-section">'
    content += section_title("绝症英雄排名 Top 10", "HIGH USAGE / LOW META PERFORMANCE")
    if profile.sick_heroes:
        content += '<div class="mr-sickness-list">'
        content += "".join(
            _sick_card(index, item)
            for index, item in enumerate(profile.sick_heroes, 1)
        )
        content += '</div>'
    else:
        content += empty_state("没有英雄同时满足场次、覆盖率和稳健劣势条件。")
    content += '</section>'
    content += _sickness_glossary()
    content += (
        '<div class="mr-meta-source mr-sickness-footer">'
        '<span>绝症与绝活使用同一套同期 Meta 基准，两个集合互斥。</span>'
        '<span>预计少赢场次不是实际损失，只是用于排序的统计估计。</span>'
        '</div>'
    )
    return page_shell(content, watermark="MY SICKNESS")


__all__ = ["build_player_sickness_html"]
