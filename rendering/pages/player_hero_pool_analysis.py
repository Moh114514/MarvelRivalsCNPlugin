"""Hero-pool structure page backed by the shared career analysis."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.analytics.models import HeroPoolAnalysis, analysis_scope_label
    from ...marvel_rivals_bot.analytics.archetypes import STYLE_LABELS, archetype_summary, product_status
except ImportError:
    from marvel_rivals_bot.analytics.models import HeroPoolAnalysis, analysis_scope_label
    from marvel_rivals_bot.analytics.archetypes import STYLE_LABELS, archetype_summary, product_status

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import escape_text


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _score(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}"


def build_player_hero_pool_analysis_html(pool: HeroPoolAnalysis) -> str:
    show_v2 = getattr(pool, "rating_version", "shadow") == "v2"
    scope = analysis_scope_label(pool.scope)
    content = page_header(
        "MY HERO POOL",
        "使用结构与核心英雄质量",
        scope,
        title_cn=f"{pool.player_name} 的{scope}英雄池",
        eyebrow="MY HERO POOL",
        meta_items=(
            ("总场次", f"{pool.total_matches:,}"),
            ("活跃英雄", pool.active_heroes),
            ("有效宽度", f"{pool.effective_pool_width:.2f}"),
        ),
    )
    if not pool.meta_available:
        content += '<div class="mr-meta-source">当前缺少同期 Meta，综合表现仅基于个人竞技/快速基准，可信度已降级。</div>'
    content += '<section class="mr-section">' + section_title("英雄池结构", "POOL STRUCTURE")
    content += metric_grid((
        ("Top 1 使用占比", _percent(pool.top1_share)),
        ("Top 3 使用占比", _percent(pool.top3_share)),
        ("有效英雄池宽度", f"{pool.effective_pool_width:.2f}"),
        ("活跃英雄", str(pool.active_heroes)),
    )) + '</section>'
    content += '<section class="mr-section">' + section_title("职责覆盖", "ROLE COVERAGE")
    content += metric_grid((
        ("捍卫者", _percent(pool.vanguard_share)),
        ("决斗家", _percent(pool.duelist_share)),
        ("策略家", _percent(pool.strategist_share)),
    )) + '</section>'
    if not show_v2:
        content += '<section class="mr-section">' + section_title("英雄池质量", "POOL QUALITY")
        content += metric_grid((
            ("核心综合表现", _score(pool.weighted_performance)),
            ("正向使用占比", _percent(pool.positive_usage_share)),
            ("负向使用占比", _percent(pool.negative_usage_share)),
        )) + '</section>'
    if show_v2:
        content += '<section class="mr-section mr-rating-v2">' + section_title("V2 画像质量", "RATING QUALITY")
        content += metric_grid((
            ("高掌握度英雄", str(pool.high_mastery_count)),
            ("高专精度英雄", str(pool.high_specialization_count)),
            ("高置信度英雄", str(pool.high_confidence_count)),
            ("负专精使用占比", _percent(pool.negative_specialization_usage_share)),
        )) + '</section>'
    content += '<section class="mr-section">' + section_title("结构结论", "STRUCTURE TAGS")
    if pool.structure_tags:
        content += '<div class="mr-meta-source">' + escape_text(" · ".join(pool.structure_tags)) + '</div>'
    else:
        content += empty_state("当前没有足够结构信号")
    content += '</section>'
    if show_v2:
        content += '<section class="mr-section mr-rating-v2">' + section_title("战术体系", "TACTICAL STYLES")
        if pool.style_shares:
            content += metric_grid(tuple((STYLE_LABELS.get(key, key), _percent(value)) for key, value in sorted(pool.style_shares.items(), key=lambda pair: -pair[1])))
            dominant_style, dominant_share = max(pool.style_shares.items(), key=lambda pair: pair[1])
            content += f'<div class="mr-meta-source">主要战斗风格：{escape_text(STYLE_LABELS.get(dominant_style, dominant_style))}（{dominant_share:.1f}%）</div>'
        else:
            content += empty_state("暂无可确认的战术体系")
        if pool.tactical_tags:
            content += '<div class="mr-meta-source">' + escape_text(" · ".join(pool.tactical_tags)) + '</div>'
        content += '</section>'
    if not show_v2:
        content += '<section class="mr-section mr-pool-core-section">' + section_title("核心英雄 Top 10", "CORE HEROES")
        if pool.core_heroes:
            content += '<div class="mr-pool-core-list">'
            for index, item in enumerate(pool.core_heroes, 1):
                content += (
                    '<article class="mr-pool-core-card">'
                    f'<div class="mr-pool-core-card__index">{index:02d}</div>'
                    '<div class="mr-pool-core-card__main">'
                    f'<div class="mr-pool-core-card__name">{escape_text(item.hero_name)}</div>'
                    f'<div class="mr-pool-core-card__stats">使用占比 {_percent(item.usage_share)} · 竞技 {item.competitive_matches} 场 · 快速 {item.quick_matches} 场</div>'
                    f'<div class="mr-pool-core-card__stats">综合表现 {_score(item.performance_index)} · 使用指数 {item.play_index:.1f} · 可信度 {escape_text(item.confidence)}</div>'
                    '</div>'
                    f'<div class="mr-pool-core-card__status">{escape_text(item.status)}</div>'
                    '</article>'
                )
            content += '</div>'
        else:
            content += empty_state("暂无达到核心英雄使用门槛的英雄")
        content += '</section>'
    if show_v2:
        content += '<section class="mr-section mr-rating-v2">' + section_title("V2 核心英雄评分", "CORE RATING")
        if pool.core_heroes:
            content += metric_grid(tuple(
                (
                    item.hero_name,
                    (
                        f"Mastery {item.rating.mastery:.1f} · Performance {item.rating.performance:.1f} · "
                        f"Specialization {'—' if item.rating.specialization is None else f'{item.rating.specialization:+.1f}'} · "
                        f"Confidence {item.rating.confidence:.2f} · {product_status(item.rating)} · {archetype_summary(item.rating.archetype)}"
                    ),
                )
                for item in pool.core_heroes
                if getattr(item, "rating", None) is not None
            )) if any(getattr(item, "rating", None) is not None for item in pool.core_heroes) else empty_state("核心英雄暂缺 V2 评分证据")
        else:
            content += empty_state("暂无达到核心英雄使用门槛的英雄")
        content += '</section>'
    footer = (
        "核心英雄按使用占比、V2 Performance 和 Confidence 排序；本页不重新抓取远程数据。"
        if getattr(pool, "rating_version", "shadow") == "v2"
        else "核心英雄按使用占比、使用指数和总场次排序；本页不重新抓取远程数据。"
    )
    content += f'<div class="mr-meta-source mr-pool-footer">{footer}</div>'
    return page_shell(content, watermark="MY HERO POOL")


__all__ = ["build_player_hero_pool_analysis_html"]
