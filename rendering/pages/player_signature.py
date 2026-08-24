"""Career-signature page, separate from the single-season Player Meta page."""

from __future__ import annotations

from typing import Any

try:
    from ...marvel_rivals_bot.analytics.models import PlayerSignatureProfile, analysis_scope_label
except ImportError:
    from marvel_rivals_bot.analytics.models import PlayerSignatureProfile, analysis_scope_label

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import escape_text


def _count(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}pp"


def _score(value: Any, *, signed: bool = False, decimals: int = 1) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number:+.{decimals}f}" if signed else f"{number:.{decimals}f}"


def _first(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        value = getattr(item, name, None)
        if value is not None:
            return value
    return default


def _hero_card(index: int, item: Any, *, career: bool) -> str:
    classification = _first(item, "classification", "status", default="绝活候选")
    tags = tuple(getattr(item, "tags", ()) or ())
    tag_text = " · ".join(str(tag) for tag in tags)
    performance_index = _first(item, "performance_index", "win_rate_delta", default=None)
    delta_class = "positive" if (performance_index or 0) >= 0 else "negative"
    quality = (
        f'<span>有效赛季 {_first(item, "effective_seasons", default="—")} · '
        f'高于环境 {_first(item, "positive_seasons", default="—")}</span>'
        if career
        else '<span>本赛季样本 · 不使用跨赛季稳定性</span>'
    )
    meta_delta = _first(item, "adjusted_meta_delta", "adjusted_delta", "win_rate_delta")
    competitive_matches = _first(item, "competitive_matches", "ranked_matches")
    actual_win_rate = _first(item, "actual_win_rate", "ranked_win_rate")
    expected_meta_win_rate = _first(item, "expected_meta_win_rate", "meta_win_rate")
    return (
        f'<article class="mr-signature-card mr-signature-card--{escape_text(delta_class)}">'
        f'<div class="mr-signature-card__index">{index:02d}</div>'
        '<div class="mr-signature-card__main">'
        '<div class="mr-signature-card__identity">'
        f'<div class="mr-signature-card__name">{escape_text(item.hero_name)}</div>'
        f'<span class="mr-signature-card__badge">{escape_text(classification)}</span>'
        '</div>'
        f'<div class="mr-signature-card__tags">{escape_text(tag_text)}</div>'
        '<div class="mr-signature-card__stats">'
        f'<span>总计 {_count(_first(item, "total_matches"))} 场</span>'
        f'<span>竞技 {_count(competitive_matches)} 场</span>'
        f'<span>使用占比 {_percent(_first(item, "usage_share"))}</span>'
        '</div></div>'
        '<div class="mr-signature-card__metrics">'
        f'<div><span>绝活指数</span><strong>{_score(getattr(item, "signature_score", None))}</strong></div>'
        f'<div><span>综合表现</span><strong>{_score(performance_index, signed=True)}</strong></div>'
        f'<div><span>竞技胜率</span><strong>{escape_text(_percent(actual_win_rate))}</strong></div>'
        f'<div><span>同期 Meta</span><strong>{escape_text(_percent(expected_meta_win_rate))}</strong></div>'
        f'<div><span>稳健领先</span><strong>{escape_text(_delta(meta_delta))}</strong></div>'
        f'<div><span>证据系数</span><strong>{_score(getattr(item, "evidence_factor", None), decimals=2)}</strong></div>'
        '</div>'
        '<div class="mr-signature-card__quality">'
        f'{quality}'
        f'<span>可信度 {escape_text(getattr(item, "confidence", "数据不足"))} · '
        f'Meta 覆盖 {_score(getattr(item, "meta_coverage", None), decimals=0)}%</span>'
        '</div></article>'
    )


def _glossary(*, career: bool) -> str:
    entries = [
        ("有效环境（有效赛季）", "该英雄在某赛季竞技模式只要出过场就计入。它表示玩家确实在这个赛季使用过该英雄，不等于一定有足够样本比较 Meta。"),
        ("同期 Meta", "RivalsMeta 的第三方统计：尽量使用玩家该赛季、该历史段位对应的英雄胜率；没有对应段位数据时才回退全段位。它不是官方数据。"),
        ("稳健领先", "玩家竞技胜率比同期 Meta 高多少个百分点，并对小样本向 0pp 拉回。比如实际高 10pp，但只有很少场次，显示的稳健领先会小于 10pp。"),
        ("长期稳定性", "在能拿到同期 Meta 的有效赛季里，玩家领先 Meta 的竞技场次占比；每个赛季最多按 20 场计权，避免某个超长赛季完全盖过其他赛季。"),
        ("可信度", "看可比较的竞技场次有多少，再结合 Meta 覆盖和历史段位覆盖评估证据强弱；场次少或覆盖低时会降为较低等级。"),
        ("绝活分类", "招牌绝活=场次充分、长期领先且稳定；强势绝活=已有较多场次并明显领先；潜力绝活=场次还少但领先明显；待验证=刚有少量正向表现；常用英雄=使用过但证据还不足。"),
        ("标签：常青绝活 / 长期专精 / 新晋绝活 / 逆版本绝活 / 本命英雄", "常青绝活=多赛季稳定领先；长期专精=使用赛季多且竞技场次多；新晋绝活=近期使用占比高且表现领先；逆版本绝活=同期 Meta 偏弱但你明显领先；本命英雄=满足最低使用量后，生涯总使用量最高。"),
        ("Meta 覆盖", "这个英雄的竞技场次里，有多少场能找到同期 Meta 数据并完成比较；覆盖越高，结论越完整。"),
        ("快速 / 竞技", "快速模式参与使用量、个人快速基准和综合表现，但不直接与 Meta 比较；竞技模式提供 Meta 对比和主要分类证据。"),
    ]
    if not career:
        entries = [
            ("赛季分类", "单赛季只使用赛季强势、赛季表现优秀、赛季待验证、赛季中性和赛季偏弱，不解释跨赛季稳定性。"),
            *(entry for entry in entries if entry[0] not in {"有效环境（有效赛季）", "长期稳定性", "标签：常青绝活 / 长期专精 / 新晋绝活 / 逆版本绝活 / 本命英雄"}),
        ]
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

    scope_label = analysis_scope_label(profile.scope)
    career = profile.scope.kind == "career"
    analysis_label = "跨赛季生涯综合分析" if career else "单赛季英雄综合分析"
    header_metrics = [
        ("竞技总场次", _count(profile.competitive_matches)),
        ("Meta 覆盖", f"{profile.meta_coverage:.0f}%"),
    ]
    if career:
        header_metrics.insert(0, ("活跃赛季", len(profile.analyzed_seasons)))
    content = page_header(
        "MY SPECIALTY",
        analysis_label,
        scope_label if scope_label == "生涯" else str(scope_label),
        title_cn=f"{profile.player_name} 的{scope_label}绝活",
        eyebrow="MY SPECIALTY",
        meta_items=tuple(header_metrics),
    )
    if profile.partial:
        failed = "、".join(profile.failed_seasons) if profile.failed_seasons else "部分历史赛季"
        content += f'<div class="mr-meta-source">{escape_text(f"提示：{failed}未能获取，以下为可用数据的阶段性结果")}</div>'
    if not profile.meta_available:
        content += '<div class="mr-meta-source">当前缺少同期 Meta，综合表现仅基于个人竞技/快速基准，可信度已降级。</div>'
    if profile.meta_source_timestamp:
        stale_text = "（部分为最近缓存）" if profile.meta_stale else ""
        content += (
            '<div class="mr-meta-source">'
            f'{escape_text(f"Meta 来源：{profile.meta_source} · 最新上游时间：{profile.meta_source_timestamp}{stale_text}")}'
            '</div>'
        )
    content += metric_grid((
        (f"{scope_label}总场次", _count(profile.total_matches)),
        (f"{scope_label}竞技场次", _count(profile.competitive_matches)),
        ("Meta 覆盖", f"{profile.meta_coverage:.0f}%"),
    ))
    content += '<section class="mr-section mr-signature-section">'
    content += section_title(
        f"{scope_label}绝活 Top 5",
        "CAREER SIGNATURE" if career else "SEASON SIGNATURE",
    )
    if profile.signature_heroes:
        content += '<div class="mr-signature-list">'
        content += "".join(
            _hero_card(index, item, career=profile.scope.kind == "career")
            for index, item in enumerate(profile.signature_heroes, 1)
        )
        content += "</div>"
    elif profile.competitive_matches <= 0:
        content += empty_state("暂无可用于竞技能力评估的数据")
    else:
        content += empty_state(
            "暂未形成数据上明确的长期绝活，以下暂无可比较候选"
            if profile.scope.kind == "career"
            else "本赛季暂无可比较的正向候选英雄"
        )
    content += '</section>'
    content += _glossary(career=profile.scope.kind == "career")
    content += (
        '<div class="mr-meta-source mr-signature-footer">'
        f'<span>{"竞技表现按各赛季玩家历史段位与同期 Meta 进行校正" if career else "竞技表现按本赛季玩家历史段位与同期 Meta 进行校正"}</span>'
        '<span>小样本已进行可信度收缩</span>'
        f'<span>{"快速模式参与个人基准，但不直接与 Meta 比较" if career else "本赛季快速模式参与个人基准，但不直接与 Meta 比较"}</span>'
        '</div>'
    )
    return page_shell(content, watermark="MY SPECIALTY")


__all__ = ["build_player_signature_html"]
