"""Single-hero view for the shared player career analysis."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.analytics.models import CareerHeroSignature, PlayerSignatureProfile, analysis_scope_label
except ImportError:
    from marvel_rivals_bot.analytics.models import CareerHeroSignature, PlayerSignatureProfile, analysis_scope_label

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
    if stats.play_time and stats.play_time > 0:
        average = lambda name: "—" if getattr(stats, name, None) is None else f"{getattr(stats, name) * 600 / stats.play_time:.1f}"
        metric_prefix = "每10分钟"
        count_metrics = (
            ("每10分钟击败", stats.kills * 600 / stats.play_time if stats.kills is not None else None),
            ("每10分钟最后一击", stats.final_hits * 600 / stats.play_time if stats.final_hits is not None else None),
            ("每10分钟死亡", stats.deaths * 600 / stats.play_time if stats.deaths is not None else None),
            ("每10分钟助攻", stats.assists * 600 / stats.play_time if stats.assists is not None else None),
        )
    else:
        average = lambda name: "—" if getattr(stats, name, None) is None or not matches else f"{getattr(stats, name) / matches:.1f}"
        metric_prefix = "场均"
        count_metrics = (
            ("击败", stats.kills),
            ("最后一击", stats.final_hits),
            ("死亡", stats.deaths),
            ("助攻", stats.assists),
        )
    return (
        '<section class="mr-section">'
        + section_title(title, "MODE DETAILS")
        + metric_grid((
            ("场次", _value(stats.matches)),
            ("胜率", _percent(stats.win_rate)),
            *tuple((label, _value(value)) for label, value in count_metrics),
            (f"{metric_prefix}伤害", average("hero_damage")),
            (f"{metric_prefix}治疗", average("heal")),
            (f"{metric_prefix}承伤", average("damage_taken")),
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
    scope_label = analysis_scope_label(profile.scope)
    is_career = profile.scope.kind == "career"
    title = f"{hero.hero_name} · {scope_label}分析"
    conclusion = hero.status
    if is_career and conclusion in {"招牌绝活", "强势绝活", "潜力绝活"}:
        description = "生涯表现高于个人基准和可用同期环境。"
    elif not is_career and conclusion in {"赛季强势", "赛季表现优秀"}:
        description = "本赛季表现高于个人基准和可用同期环境。"
    elif conclusion in {"绝症候选", "赛季偏弱", "相对弱势"}:
        description = "当前使用量和证据显示相对表现偏弱。"
    else:
        description = "当前处于中性区或证据不足。"
    header_rating = getattr(hero, "rating", None) if profile.rating_version == "v2" else None
    header_metrics = (
        (("Mastery", f"{header_rating.mastery:.1f}"), ("Performance", f"{header_rating.performance:.1f}"), ("Confidence", f"{header_rating.confidence:.2f}"))
        if header_rating is not None
        else (("综合表现", f"{hero.performance_index:+.1f}"), ("使用指数", f"{hero.play_index:.1f}"), ("可信度", hero.confidence))
    )
    content = page_header(
        "MY HERO ANALYSIS",
        description,
        title,
        title_cn=title,
        meta_items=header_metrics,
    )
    content += '<section class="mr-section">' + section_title(conclusion, "CONCLUSION")
    rating = getattr(hero, "rating", None) if profile.rating_version == "v2" else None
    usage_metrics = [
        ("绝活指数", f"{hero.signature_score:.1f}"),
        ("绝症指数", f"{hero.sickness_score:.1f}"),
        ("总场次", _value(hero.total_matches)),
        ("竞技场次", _value(hero.competitive_matches)),
        ("快速场次", _value(hero.quick_matches)),
    ]
    if is_career:
        usage_metrics.append(("活跃赛季", _value(hero.active_seasons)))
    if rating is not None:
        usage_metrics = [
            ("Mastery", f"{rating.mastery:.1f}"),
            ("Performance", f"{rating.performance:.1f}"),
            ("Specialization", "—" if rating.specialization is None else f"{rating.specialization:+.1f}"),
            ("Confidence", f"{rating.confidence:.2f}"),
            *usage_metrics[2:],
        ]
    content += metric_grid(tuple(usage_metrics)) + '</section>'
    rating = getattr(hero, "rating", None) if profile.rating_version == "v2" else None
    if rating is not None:
        dimensions = " / ".join(
            f"{key.upper()} {value:.1f}" if value is not None else f"{key.upper()} —"
            for key, value in rating.dimensions.items()
        )
        content += (
            '<section class="mr-section mr-rating-v2">'
            + section_title("评分 V2", "RATING V2")
            + metric_grid((
                ("Mastery", f"{rating.mastery:.1f}"),
                ("Performance", f"{rating.performance:.1f}"),
                ("Specialization", "—" if rating.specialization is None else f"{rating.specialization:+.1f}"),
                ("Confidence", f"{rating.confidence:.2f}"),
                ("Outcome", _value(rating.outcome)),
                ("Combat", _value(rating.combat)),
                ("Consistency", _value(rating.consistency)),
                ("Experience", f"{rating.experience:.1f}"),
            ))
            + f'<div class="mr-meta-source">战术原型：{escape_text({"dive": "切入", "brawl": "缠斗", "poke": "消耗"}.get(rating.archetype.primary_style.value, rating.archetype.primary_style.value))} / {escape_text(rating.archetype.function.value)} · {escape_text(dimensions)}</div>'
            + '</section>'
        )
    content += f'<section class="mr-section{" mr-v2-legacy-environment" if profile.rating_version == "v2" else ""}">' + section_title("竞技环境比较", "ENVIRONMENT")
    content += metric_grid((
        ("可比较竞技胜率", _percent(hero.comparable_competitive_win_rate)),
        ("同期同段位 Meta", _percent(hero.expected_meta_win_rate)),
        ("原始环境差值", _delta(hero.raw_meta_delta if hero.raw_meta_delta is not None else hero.raw_delta)),
        ("稳健环境差值", _delta(
            hero.adjusted_meta_delta
            if hero.adjusted_meta_delta is not None else hero.adjusted_delta
        )),
        ("个人竞技相对表现", _delta(hero.personal_competitive_delta)),
        ("个人快速相对表现", _delta(hero.personal_quick_delta)),
        ("Meta 覆盖", f"{hero.meta_coverage:.0f}%"),
        ("证据修正", f"{hero.evidence_factor:.2f}"),
    )) + '</section>'
    if not profile.meta_available:
        content += '<div class="mr-meta-source">当前缺少同期 Meta，综合表现仅基于个人竞技/快速基准，可信度已降级。</div>'
    content += _mode_block("竞技详细数据", hero.competitive_stats)
    content += _mode_block("快速详细数据", hero.quick_stats)
    return page_shell(content, watermark="MY HERO ANALYSIS")


__all__ = ["build_player_hero_analysis_html"]
