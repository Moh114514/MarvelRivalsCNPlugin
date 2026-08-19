"""Career-signature page, separate from the single-season Player Meta page."""

from __future__ import annotations

from typing import Any

try:
    from ...marvel_rivals_bot.analytics.models import PlayerSignatureProfile
except ImportError:
    from marvel_rivals_bot.analytics.models import PlayerSignatureProfile

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import escape_text


def _count(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}pp"


def _hero_card(index: int, item: Any) -> str:
    tags = " · ".join((item.classification, *item.tags))
    delta_class = "positive" if (item.adjusted_delta or 0) >= 0 else "negative"
    return (
        f'<article class="mr-signature-card mr-signature-card--{escape_text(delta_class)}">'
        f'<div class="mr-signature-card__index">{index:02d}</div>'
        '<div class="mr-signature-card__main">'
        f'<div class="mr-signature-card__name">{escape_text(item.hero_name)}</div>'
        f'<div class="mr-signature-card__tags">{escape_text(tags)}</div>'
        '<div class="mr-signature-card__stats">'
        f'<span>总计 {_count(item.total_matches)} 场</span>'
        f'<span>竞技 {_count(item.competitive_matches)} 场</span>'
        f'<span>使用占比 {_percent(item.usage_share)}</span>'
        '</div></div>'
        '<div class="mr-signature-card__metrics">'
        f'<div><span>竞技胜率</span><strong>{escape_text(_percent(item.actual_win_rate))}</strong></div>'
        f'<div><span>同期 Meta</span><strong>{escape_text(_percent(item.expected_meta_win_rate))}</strong></div>'
        f'<div><span>稳健领先</span><strong>{escape_text(_delta(item.adjusted_delta))}</strong></div>'
        f'<div><span>长期稳定性</span><strong>{escape_text(_percent(item.stability))}</strong></div>'
        '</div>'
        '<div class="mr-signature-card__quality">'
        f'<span>有效赛季 {item.effective_seasons} · 高于环境 {item.positive_seasons}</span>'
        f'<span>可信度 {escape_text(item.confidence)} · Meta 覆盖 {item.meta_coverage:.0f}%</span>'
        '</div></article>'
    )


def _glossary() -> str:
    entries = (
        ("有效环境（有效赛季）", "该英雄在某赛季竞技模式只要出过场就计入。它表示玩家确实在这个赛季使用过该英雄，不等于一定有足够样本比较 Meta。"),
        ("同期 Meta", "RivalsMeta 的第三方统计：尽量使用玩家该赛季、该历史段位对应的英雄胜率；没有对应段位数据时才回退全段位。它不是官方数据。"),
        ("稳健领先", "玩家竞技胜率比同期 Meta 高多少个百分点，并对小样本向 0pp 拉回。比如实际高 10pp，但只有很少场次，显示的稳健领先会小于 10pp。"),
        ("长期稳定性", "在能拿到同期 Meta 的有效赛季里，玩家领先 Meta 的竞技场次占比；每个赛季最多按 20 场计权，避免某个超长赛季完全盖过其他赛季。"),
        ("可信度", "看可比较的竞技场次有多少，再结合 Meta 覆盖和历史段位覆盖评估证据强弱；场次少或覆盖低时会降为较低等级。"),
        ("绝活分类", "招牌绝活=场次充分、长期领先且稳定；强势绝活=已有较多场次并明显领先；潜力绝活=场次还少但领先明显；待验证=刚有少量正向表现；常用英雄=使用过但证据还不足。"),
        ("标签：常青绝活 / 长期专精 / 新晋绝活 / 逆版本绝活 / 本命英雄", "常青绝活=多赛季稳定领先；长期专精=使用赛季多且竞技场次多；新晋绝活=近期使用占比高且表现领先；逆版本绝活=同期 Meta 偏弱但你明显领先；本命英雄=满足最低使用量后，生涯总使用量最高。"),
        ("Meta 覆盖", "这个英雄的竞技场次里，有多少场能找到同期 Meta 数据并完成比较；覆盖越高，结论越完整。"),
        ("快速 / 竞技", "快速模式只用来统计使用量和本命判断；竞技模式才用于胜率、Meta 对比、稳定性和绝活分类。"),
    )
    cards = "".join(
        f'<article class="mr-signature-glossary__item">'
        f'<strong>{escape_text(term)}</strong>'
        f'<span>{escape_text(description)}</span>'
        f'</article>'
        for term, description in entries
    )
    return (
        '<section class="mr-section mr-signature-glossary-section">'
        + section_title("名词说明", "READ THE METRICS")
        + f'<div class="mr-signature-glossary">{cards}</div>'
        + '</section>'
    )


def build_player_signature_html(profile: PlayerSignatureProfile) -> str:
    """Render V2 career data; retain a lazy legacy fallback for integrations."""

    if not isinstance(profile, PlayerSignatureProfile):
        from .player_meta import build_player_signature_html as legacy_builder

        return legacy_builder(profile)

    first = profile.first_season or "未知"
    latest = profile.latest_season or first
    content = page_header(
        "MY SPECIALTY",
        "跨赛季生涯综合分析",
        f"{first} — {latest}",
        title_cn=f"{profile.player_name} 的生涯绝活",
        eyebrow="MY SPECIALTY",
        meta_items=(
            ("活跃赛季", len(profile.analyzed_seasons)),
            ("竞技总场次", _count(profile.competitive_matches)),
            ("Meta 覆盖", f"{profile.meta_coverage:.0f}%"),
        ),
    )
    if profile.partial:
        failed = "、".join(profile.failed_seasons) if profile.failed_seasons else "部分历史赛季"
        content += f'<div class="mr-meta-source">{escape_text(f"提示：{failed}未能获取，以下为可用数据的阶段性结果")}</div>'
    if profile.meta_source_timestamp:
        stale_text = "（部分为最近缓存）" if profile.meta_stale else ""
        content += (
            '<div class="mr-meta-source">'
            f'{escape_text(f"Meta 来源：{profile.meta_source} · 最新上游时间：{profile.meta_source_timestamp}{stale_text}")}'
            '</div>'
        )
    content += metric_grid((
        ("生涯总场次", _count(profile.total_matches)),
        ("竞技总场次", _count(profile.competitive_matches)),
        ("Meta 覆盖", f"{profile.meta_coverage:.0f}%"),
    ))
    content += '<section class="mr-section mr-signature-section">'
    content += section_title("生涯绝活 Top 5", "CAREER SIGNATURE")
    if profile.signature_heroes:
        content += '<div class="mr-signature-list">'
        content += "".join(_hero_card(index, item) for index, item in enumerate(profile.signature_heroes, 1))
        content += "</div>"
    elif profile.competitive_matches <= 0:
        content += empty_state("暂无可用于竞技能力评估的数据")
    else:
        content += empty_state("暂未形成数据上明确的长期绝活，以下暂无可比较候选")
    content += '</section>'
    content += _glossary()
    content += (
        '<div class="mr-meta-source mr-signature-footer">'
        '<span>竞技表现按各赛季玩家历史段位与同期 Meta 进行校正</span>'
        '<span>小样本已进行可信度收缩</span>'
        '<span>快速模式仅参与英雄使用量统计</span>'
        '</div>'
    )
    return page_shell(content, watermark="MY SPECIALTY")


__all__ = ["build_player_signature_html"]
