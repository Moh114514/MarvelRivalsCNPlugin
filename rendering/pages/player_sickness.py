"""Career sickness page for high-use heroes with relatively weak performance."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.analytics.models import PlayerSignatureProfile, analysis_scope_label
    from ...marvel_rivals_bot.analytics.signature_rules import sickness_severity
except ImportError:
    from marvel_rivals_bot.analytics.models import PlayerSignatureProfile, analysis_scope_label
    from marvel_rivals_bot.analytics.signature_rules import sickness_severity

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import escape_text


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}pp"


def _meta_disadvantage(item) -> float | None:
    value = getattr(item, "meta_disadvantage", None)
    if value is not None:
        return float(value)
    raw_delta = getattr(item, "raw_meta_delta", getattr(item, "meta_delta", None))
    return max(-float(raw_delta), 0.0) if raw_delta is not None else None


def _sick_card(index: int, item) -> str:
    sickness_score = float(getattr(item, "sickness_score", getattr(item, "sick_score", 0.0)) or 0.0)
    return (
        '<article class="mr-sickness-card">'
        f'<div class="mr-sickness-card__index">{index:02d}</div>'
        '<div class="mr-sickness-card__main">'
        f'<div class="mr-sickness-card__name">{escape_text(item.hero_name)}</div>'
        '<div class="mr-sickness-card__stats">'
        f'<span>总计 {item.total_matches:,} 场</span>'
        f'<span>竞技 {item.competitive_matches:,} 场</span>'
        f'<span>快速 {item.quick_matches:,} 场</span>'
        f'<span>使用占比 {item.usage_share:.1f}%</span>'
        f'<span>竞技胜率 {escape_text(_percent(item.actual_win_rate))}</span>'
        f'<span>快速胜率 {escape_text(_percent(item.quick_win_rate))}</span>'
        f'<span>同期 Meta {escape_text(_percent(item.expected_meta_win_rate))}</span>'
        '</div>'
        '<div class="mr-sickness-card__detail">'
        f'<span>Meta 劣势 {escape_text(_delta(_meta_disadvantage(item)))}</span>'
        f'<span>个人竞技相对表现 {escape_text(_delta(item.personal_competitive_delta))}</span>'
        f'<span>个人快速相对表现 {escape_text(_delta(item.personal_quick_delta))}</span>'
        f'<span>稳健环境差值 {escape_text(_delta(item.adjusted_delta))}</span>'
        f'<span>Meta 覆盖 {item.meta_coverage:.0f}%</span>'
        f'<span>可信度 {escape_text(item.confidence)}</span>'
        '</div>'
        '</div>'
        '<div class="mr-sickness-card__score">'
        '<span>绝症指数</span>'
        f'<strong>{sickness_score:.1f}</strong>'
        f'<small>{escape_text(sickness_severity(sickness_score))} · 使用指数 {item.play_index:.1f} · 弱势表现 {item.weakness_index:.1f}</small>'
        f'<small>综合表现 {item.performance_index:+.1f}</small>'
        f'<small>状态 {escape_text(getattr(item, "status", "绝症候选"))}</small>'
        '</div>'
        '</article>'
    )


def _sickness_glossary() -> str:
    entries = (
        ("使用指数", "把竞技场次、快速场次和使用占比分别换算成 0—100 分，再按 40%、20%、40% 加权；分数越高，说明你越常回到这个英雄。"),
        ("弱势表现", "统一取 max(-Performance Index, 0)，把 Meta、个人竞技和个人快速的可用相对表现合成为一个负向轴。"),
        ("绝症指数", "使用指数 × 弱势表现 ÷ 100 × 证据修正。它是“玩得多且相对表现差”的排序分，不是医学诊断，也不是实际少赢场次。"),
        ("Meta / 个人相对表现", "Meta 相对表现是低于同期环境多少个百分点；个人相对表现是低于自己其他英雄平均表现多少个百分点，采用不包含当前英雄的留一法，并按小样本先验收缩。"),
        ("候选范围", "总场次至少 10，或竞技至少 5，或快速至少 20；Performance ≤ -10 且绝症指数 > 0 才进入绝症榜，-10 到 +10 是中性区。"),
        ("为什么没有凑满 Top 10", "这是最多 10 名的相对排名；没有足够使用量或胜率证据的英雄不会被硬塞进来，低分也不等于确诊。"),
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
    scope_label = analysis_scope_label(profile.scope)
    content = page_header(
        "MY SICKNESS",
        "高使用量相对弱势分析",
        scope_label if scope_label == "生涯" else str(scope_label),
        title_cn=f"{profile.player_name} 的{scope_label}绝症",
        eyebrow="MY SICKNESS",
        meta_items=(
            ("总场次", f"{profile.total_matches:,}"),
            ("竞技总场次", f"{profile.competitive_matches:,}"),
            ("候选数量", len(profile.sick_heroes)),
            ("Meta 覆盖", f"{profile.meta_coverage:.0f}%"),
        ),
    )
    if profile.partial:
        content += (
            '<div class="mr-meta-source">'
            '部分历史赛季或 Meta 数据不可用，以下仍会使用可用信号进行相对排名。'
            '</div>'
        )
    if not profile.meta_available:
        content += '<div class="mr-meta-source">当前缺少同期 Meta，综合表现仅基于个人竞技/快速基准，可信度已降级。</div>'
    if profile.meta_source_timestamp:
        stale_text = "（部分使用最近缓存）" if profile.meta_stale else ""
        content += (
            '<div class="mr-meta-source">'
            f'{escape_text(f"Meta 来源：{profile.meta_source} · 最新上游时间：{profile.meta_source_timestamp}{stale_text}")}'
            '</div>'
        )
    content += metric_grid((
        ("总场次", f"{profile.total_matches:,}"),
        ("竞技总场次", f"{profile.competitive_matches:,}"),
        ("绝症候选", len(profile.sick_heroes)),
        ("Meta 覆盖", f"{profile.meta_coverage:.0f}%"),
    ))
    content += '<section class="mr-section mr-sickness-section">'
    content += section_title("绝症英雄排名 Top 10", "HIGH USE / RELATIVE WEAKNESS")
    if profile.sick_heroes:
        content += '<div class="mr-sickness-list">'
        content += "".join(
            _sick_card(index, item)
            for index, item in enumerate(profile.sick_heroes, 1)
        )
        content += '</div>'
    else:
        content += empty_state("目前没有可用于相对排名的候选英雄。")
    content += '</section>'
    content += _sickness_glossary()
    content += (
        '<div class="mr-meta-source mr-sickness-footer">'
        '<span>本页最多展示 Top 10；绝症指数只表示相对排序，不代表实际损失或医学意义上的确诊。</span>'
        f'<span>{"快速模式是辅助信号，核心仍是生涯使用量与相对表现。" if profile.scope.kind == "career" else "快速模式是辅助信号，核心仍是本赛季使用量与相对表现。"}</span>'
        '</div>'
    )
    return page_shell(content, watermark="MY SICKNESS")


__all__ = ["build_player_sickness_html"]
