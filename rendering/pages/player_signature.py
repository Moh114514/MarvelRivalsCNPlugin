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
        ("有效环境（有效赛季）", "该英雄在某赛季竞技至少 5 场，并且能与同期 Meta 胜率比较的样本。优先使用历史段位 Meta，缺失时才回退全段位。"),
        ("Meta 覆盖", "该英雄竞技场次中，成功找到同期 Meta 数据并完成比较的比例；覆盖不足会降低可信度。"),
        ("同期 Meta", "RivalsMeta 第三方统计中，与玩家该赛季、该段位环境对应的英雄预期胜率。"),
        ("稳健领先", "玩家竞技胜率减同期 Meta 胜率，并用 20 场先验向 0pp 收缩，降低小样本偶然性。"),
        ("长期稳定性", "各个有效赛季中领先 Meta 的竞技场次占比；每个赛季最多计 20 场，避免单个赛季压过长期表现。"),
        ("可信度", "根据可比较竞技场次分级，并结合 Meta 覆盖和历史段位覆盖进行降级。"),
        ("绝活分类", "招牌、强势、潜力、待验证和常用根据竞技样本量、稳健领先、稳定性和 Meta 覆盖综合判定，不是官方称号。"),
        ("快速 / 竞技", "快速模式只参与使用量和本命判断；竞技模式才参与胜率、Meta 对比和绝活分类。"),
        ("本命英雄", "在满足最低使用量的前提下，生涯总使用量最高的英雄；它不等同于绝活分类。"),
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
