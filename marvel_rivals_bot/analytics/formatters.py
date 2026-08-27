"""Simplified-Chinese formatters for Player × Meta ViewModels."""

from __future__ import annotations

from datetime import datetime

from .models import (
    CareerHeroSignature,
    HeroPoolAnalysis,
    PlayerHeroMetaComparison,
    PlayerMetaProfile,
    PlayerSignatureProfile,
    analysis_scope_label,
)
from .archetypes import STYLE_LABELS, archetype_summary, product_status
from .signature_rules import sickness_severity


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}pp"


def _count(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def _hours(value: float | None) -> str:
    return "—" if value is None else f"{value / 3600:.1f} 小时"


def _mode_analysis_lines(title: str, mode) -> list[str]:
    if mode is None:
        return [title, "暂无数据"]
    matches = getattr(mode, "matches", None)
    def average(field: str) -> str:
        value = getattr(mode, field, None)
        play_time = getattr(mode, "play_time", None)
        if value is None:
            return "—"
        if play_time and play_time > 0:
            return f"{value * 600 / play_time:.1f}"
        return "—" if not matches else f"{value / matches:.1f}"
    metric_prefix = "每10分钟" if getattr(mode, "play_time", None) and mode.play_time > 0 else "场均"
    if getattr(mode, "play_time", None) and mode.play_time > 0:
        count_values = [
            getattr(mode, "kills", None), getattr(mode, "final_hits", None),
            getattr(mode, "deaths", None), getattr(mode, "assists", None),
        ]
        count_values = [value * 600 / mode.play_time if value is not None else None for value in count_values]
        count_label = "每10分钟击败 / 最后一击 / 死亡 / 助攻："
    else:
        count_values = [
            getattr(mode, "kills", None), getattr(mode, "final_hits", None),
            getattr(mode, "deaths", None), getattr(mode, "assists", None),
        ]
        count_label = "击败 / 最后一击 / 死亡 / 助攻："
    return [
        title,
        f"场次：{_count(matches)}｜胜率：{_percent(getattr(mode, 'win_rate', None))}",
        count_label
        + f"{_count(count_values[0])} / {_count(count_values[1])} / "
        f"{_count(count_values[2])} / {_count(count_values[3])}",
        f"{metric_prefix}伤害 / 治疗 / 承伤：{average('hero_damage')} / {average('heal')} / {average('damage_taken')}",
        f"游戏时长：{_hours(getattr(mode, 'play_time', None))}｜MVP：{_count(getattr(mode, 'mvp', None))}｜SVP：{_count(getattr(mode, 'svp', None))}",
    ]


def format_player_hero_analysis(profile: PlayerSignatureProfile, hero: CareerHeroSignature) -> str:
    """Render one hero from the same ViewModel consumed by list commands."""

    v2_rating = (
        getattr(hero, "rating", None)
        if getattr(profile, "rating_version", "shadow") == "v2"
        else None
    )

    scope = profile.scope
    scope_label = analysis_scope_label(scope)
    is_career = scope.kind == "career"
    performance = float(hero.performance_index or 0.0)
    conclusion = hero.status
    if is_career and conclusion in {"招牌绝活", "强势绝活", "潜力绝活"}:
        explanation = "这是你在生涯范围内表现高于个人基准和可用同期环境的英雄。"
    elif not is_career and conclusion in {"赛季强势", "赛季表现优秀"}:
        explanation = "这是你在本赛季表现高于个人基准和可用同期环境的英雄。"
    elif conclusion in {"绝症候选", "赛季偏弱", "相对弱势"}:
        explanation = "当前使用量和证据显示，它相对个人同模式基准及可用环境表现偏弱。"
    else:
        explanation = "当前数据处于中性区或证据不足，暂不归入正向或负向榜单。"
    if v2_rating is not None:
        lines = [
            f"{hero.hero_name} · {scope_label}分析",
            f"玩家：{profile.player_name}（UID：{profile.uid}）",
            "",
            product_status(v2_rating),
            explanation,
            "V2 评分",
            *_rating_lines(v2_rating),
            "",
            "生涯使用" if is_career else "本赛季使用",
            f"总场次：{_count(hero.total_matches)}｜竞技：{_count(hero.competitive_matches)}｜快速：{_count(hero.quick_matches)}",
            *( [f"活跃赛季：{hero.active_seasons}"] if is_career else [] ),
        ]
        if not getattr(profile, "meta_available", True):
            lines.append("提示：当前缺少同期 Meta，可信度已降级。")
        lines.extend(_mode_analysis_lines("竞技详细数据", hero.competitive_stats))
        lines.append("")
        lines.extend(_mode_analysis_lines("快速详细数据", hero.quick_stats))
        return "\n".join(lines)
    lines = [
        f"{hero.hero_name} · {scope_label}分析",
        f"玩家：{profile.player_name}（UID：{profile.uid}）",
        "",
        conclusion,
        explanation,
        f"绝活指数：{hero.signature_score:.1f}｜绝症指数：{hero.sickness_score:.1f}",
        f"综合表现：{performance:+.1f}｜使用指数：{hero.play_index:.1f}｜可信度：{hero.confidence}",
        "",
        "生涯使用" if is_career else "本赛季使用",
        f"总场次：{_count(hero.total_matches)}｜竞技：{_count(hero.competitive_matches)}｜快速：{_count(hero.quick_matches)}",
        *( [f"活跃赛季：{hero.active_seasons}"] if is_career else [] ),
        "",
        "竞技环境比较",
        f"可比较竞技胜率：{_percent(hero.comparable_competitive_win_rate)}｜同期同段位 Meta：{_percent(hero.expected_meta_win_rate)}",
        f"原始环境差值：{_delta(hero.raw_meta_delta if hero.raw_meta_delta is not None else hero.raw_delta)}｜稳健环境差值：{_delta(hero.adjusted_meta_delta if hero.adjusted_meta_delta is not None else hero.adjusted_delta)}",
        f"个人竞技相对表现：{_delta(hero.personal_competitive_delta)}",
        f"个人快速相对表现：{_delta(hero.personal_quick_delta)}",
        f"Meta 覆盖：{hero.meta_coverage:.1f}%｜证据修正：{hero.evidence_factor:.2f}",
        "",
    ]
    if v2_rating is not None:
        lines.extend(_rating_lines(v2_rating))
    if not getattr(profile, "meta_available", True):
        lines.insert(7, "提示：当前缺少同期 Meta，综合表现仅基于个人竞技/快速基准，可信度已降级。")
    lines.extend(_mode_analysis_lines("竞技详细数据", hero.competitive_stats))
    lines.append("")
    lines.extend(_mode_analysis_lines("快速详细数据", hero.quick_stats))
    return "\n".join(lines)


def _timestamp(value: datetime | None) -> str:
    if value is None:
        return "未知"
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def _context(profile: PlayerMetaProfile) -> list[str]:
    lines = [
        f"玩家：{profile.player_name}（UID：{profile.uid}）",
        f"当前段位：{profile.cn_rank_label} · Meta 环境：{profile.meta_rank_label}",
        f"赛季：{profile.season_label}",
        f"数据来源：{profile.source} · 更新时间：{_timestamp(profile.source_timestamp)}",
    ]
    if profile.stale:
        lines.append("当前上游暂不可用，以下展示最近缓存数据")
    return lines


def _hero_line(index: int, result, metric: str) -> str:
    value = getattr(result, metric)
    if metric == "matches":
        value_text = f"{value:,} 场"
    else:
        value_text = _percent(value)
    return f"{index}. {result.hero_name}  {value_text}"


def format_player_environment(profile: PlayerMetaProfile) -> str:
    lines = [f"我的环境 | {profile.season_label} | {profile.meta_rank_label}", *_context(profile)]
    overview = profile.environment
    if overview is None:
        return "\n".join(lines + ["", "暂无可用的段位环境数据。"])
    sections = (
        ("胜率最高", "win_rate", overview.win_rate),
        ("最常见", "pick_rate", overview.pick_rate),
        ("最高 Ban", "ban_rate", overview.ban_rate),
    )
    for title, metric, items in sections:
        lines.extend(("", title))
        lines.extend(_hero_line(index, result, metric) for index, result in enumerate(items, 1))
    return "\n".join(lines)


def _comparison_line(index: int, item: PlayerHeroMetaComparison) -> list[str]:
    return [
        f"{index}. {item.hero_name}",
        f"总场次：{_count(item.total_matches)} · 快速：{_count(item.quick_matches)} · 竞技：{_count(item.ranked_matches)}",
        f"竞技占比：{_percent(item.ranked_share)} · 竞技胜率：{_percent(item.ranked_win_rate)}",
        f"同段位 Meta：{_percent(item.meta_win_rate)} · 差值：{_delta(item.win_rate_delta)}",
        f"选取率：{_percent(item.meta_pick_rate)} · Ban率：{_percent(item.meta_ban_rate)}",
    ]


def format_player_hero_pool(profile: PlayerMetaProfile) -> str:
    lines = [f"我的英雄池 | {profile.season_label} | {profile.meta_rank_label}", *_context(profile)]
    if not profile.hero_pool:
        return "\n".join(lines + ["", "暂无可用于比较的个人英雄数据。"])
    lines.extend(("", "英雄池熟悉度 × 竞技验证"))
    for index, item in enumerate(profile.hero_pool, 1):
        lines.extend(_comparison_line(index, item))
    return "\n".join(lines)


def format_player_hero_pool_analysis(pool: HeroPoolAnalysis) -> str:
    scope = analysis_scope_label(pool.scope)
    show_v2 = getattr(pool, "rating_version", "shadow") == "v2"
    weighted_performance = (
        "—"
        if pool.weighted_performance is None
        else f"{pool.weighted_performance:+.1f}"
    )
    lines = [
        f"我的英雄池｜{scope}",
        f"玩家：{pool.player_name}（UID：{pool.uid}）",
        f"统计范围：{scope}",
        "",
        "英雄池结构",
        f"总场次：{_count(pool.total_matches)}｜活跃英雄：{pool.active_heroes}｜有效英雄池宽度：{pool.effective_pool_width:.2f}",
        f"Top 1 使用占比：{pool.top1_share:.1f}%｜Top 3 使用占比：{pool.top3_share:.1f}%",
        f"捍卫者：{pool.vanguard_share:.1f}%｜决斗家：{pool.duelist_share:.1f}%｜策略家：{pool.strategist_share:.1f}%",
        "",
        "英雄池质量",
        (
            f"V2 高掌握英雄：{pool.high_mastery_count}｜高专精英雄：{pool.high_specialization_count}｜高可信英雄：{pool.high_confidence_count}"
            if show_v2
            else f"核心英雄综合表现：{weighted_performance}｜正向使用占比：{pool.positive_usage_share:.1f}%｜负向使用占比：{pool.negative_usage_share:.1f}%"
        ),
    ]
    style_shares = getattr(pool, "style_shares", {}) or {} if show_v2 else {}
    tactical_tags = getattr(pool, "tactical_tags", ()) or () if show_v2 else ()
    if style_shares:
        style_labels = {"dive": "切入", "brawl": "缠斗", "poke": "消耗"}
        lines.extend(("", "战术体系", "｜".join(f"{style_labels.get(key, key)} {value:.1f}%" for key, value in sorted(style_shares.items(), key=lambda pair: -pair[1]))))
        dominant_style, dominant_share = max(style_shares.items(), key=lambda pair: pair[1])
        lines.append(f"主要战斗风格：{STYLE_LABELS.get(dominant_style, dominant_style)}（{dominant_share:.1f}%）")
    if tactical_tags:
        lines.append("战术标签：" + "｜".join(tactical_tags))
    if not pool.meta_available:
        lines.append("提示：当前缺少同期 Meta，综合表现仅基于个人竞技/快速基准，可信度已降级。")
    if pool.structure_tags:
        lines.extend(("", "结构结论：" + " · ".join(pool.structure_tags)))
    lines.extend(("", f"核心英雄 Top {len(pool.core_heroes)}"))
    if not pool.core_heroes:
        lines.append("暂无达到核心英雄使用门槛的英雄。")
    if show_v2:
        for index, item in enumerate(pool.core_heroes, 1):
            rating = getattr(item, "rating", None)
            if rating is None:
                continue
            specialization = "—" if rating.specialization is None else f"{rating.specialization:+.1f}"
            lines.extend((
                f"{index}. {item.hero_name}｜使用占比 {item.usage_share:.1f}%｜竞技 {_count(item.competitive_matches)} 场｜快速 {_count(item.quick_matches)} 场",
                f"Mastery {rating.mastery:.1f}｜Performance {rating.performance:.1f}｜Specialization {specialization}｜Confidence {rating.confidence:.2f}",
                f"战术原型：{archetype_summary(rating.archetype)}",
                f"Outcome {_format_rating_value(rating.outcome)}｜Combat {_format_rating_value(rating.combat)}｜Consistency {_format_rating_value(rating.consistency)}｜Experience {rating.experience:.1f}",
            ))
        return "\n".join(lines)
    for index, item in enumerate(pool.core_heroes, 1):
        lines.extend((
            f"{index}. {item.hero_name}｜使用占比 {item.usage_share:.1f}%｜竞技 {item.competitive_matches} 场｜快速 {item.quick_matches} 场",
            f"综合表现：{item.performance_index:+.1f}｜使用指数：{item.play_index:.1f}｜可信度：{item.confidence}｜状态：{item.status}",
        ))
    return "\n".join(lines)


def format_player_signature(profile: PlayerMetaProfile) -> str:
    if isinstance(profile, PlayerSignatureProfile):
        return _format_signature_profile(profile)
    lines = [
        f"我的绝活 | {profile.season_label} | {profile.meta_rank_label}",
        *_context(profile),
        f"规则：总场次 ≥ {profile.minimum_matches}，竞技场次 ≥ {profile.minimum_ranked_matches}，且竞技胜率高于同段位 Meta",
    ]
    if not profile.signature_heroes:
        return "\n".join(lines + ["", "暂无同时满足总场次、竞技场次和胜率要求的英雄。"])
    lines.extend(("", "你的绝活"))
    for index, item in enumerate(profile.signature_heroes, 1):
        lines.extend(_comparison_line(index, item))
    return "\n".join(lines)


def _format_signature_profile(profile: PlayerSignatureProfile) -> str:
    analysis_scope = getattr(profile, "scope", None)
    scope = analysis_scope_label(analysis_scope)
    show_v2 = getattr(profile, "rating_version", "shadow") == "v2"
    lines = [
        f"我的绝活｜{scope}分析",
        f"玩家：{profile.player_name}（UID：{profile.uid}）",
        f"统计范围：{scope}",
        f"Meta 覆盖：{profile.meta_coverage:.0f}%",
        f"{scope}总场次：{_count(profile.total_matches)} · 竞技：{_count(profile.competitive_matches)}",
    ]
    if profile.partial:
        lines.append("提示：部分历史赛季未能获取，以下为可用数据的阶段性结果")
    if not getattr(profile, "meta_available", True):
        lines.append("提示：当前缺少同期 Meta，综合表现仅基于个人竞技/快速基准，可信度已降级")
    if profile.meta_source_timestamp:
        stale_text = "（部分为最近缓存）" if profile.meta_stale else ""
        lines.append(
            f"Meta 来源：{profile.meta_source} · 最新上游时间：{profile.meta_source_timestamp}{stale_text}"
        )
    if profile.failed_seasons:
        lines.append(f"跳过赛季：{'、'.join(profile.failed_seasons)}")
    if not profile.signature_heroes:
        if profile.competitive_matches <= 0:
            lines.extend(("", "暂无可用于竞技能力评估的数据。"))
        else:
            lines.extend((
                "",
                "暂未形成数据上明确的长期绝活，以下为最接近的英雄。"
                if scope == "生涯"
                else "本赛季暂无达到正向候选门槛的英雄。",
            ))
        return "\n".join(lines)
    if show_v2:
        lines.extend(("", f"{scope}绝活 Top 5"))
        for index, item in enumerate(profile.signature_heroes, 1):
            rating = getattr(item, "rating", None)
            if rating is None:
                lines.extend((f"{index}. {item.hero_name}", "V2 评分暂不可用"))
                continue
            lines.extend((
                f"{index}. {item.hero_name}",
                f"{product_status(rating)}｜使用占比：{item.usage_share:.1f}%｜竞技：{_count(item.competitive_matches)} 场",
                f"战术原型：{archetype_summary(rating.archetype)}",
                *_rating_lines(rating),
            ))
        return "\n".join(lines)
    lines.extend(("", f"{scope}绝活 Top 5"))
    for index, item in enumerate(profile.signature_heroes, 1):
        tags = " · ".join((item.classification, *item.tags))
        lines.extend(
            (
                f"{index}. {item.hero_name}",
                tags,
                f"总计：{_count(item.total_matches)} 场 · 竞技：{_count(item.competitive_matches)} 场",
                f"竞技胜率：{_percent(item.actual_win_rate)} · 同期 Meta：{_percent(item.expected_meta_win_rate)}",
                f"环境领先：{_delta(item.raw_meta_delta if item.raw_meta_delta is not None else item.raw_delta)} · 稳健领先：{_delta(item.adjusted_meta_delta if item.adjusted_meta_delta is not None else item.adjusted_delta)}",
                f"综合表现：{item.performance_index:+.1f} · 使用指数：{item.play_index:.1f} · 证据修正：{item.evidence_factor:.2f} · 绝活指数：{item.signature_score:.1f}",
                *([f"有效赛季：{item.effective_seasons} · 高于环境：{item.positive_seasons} · 稳定性：{_percent(item.stability)}"] if scope == "生涯" else ["本赛季样本可信度：" + item.confidence]),
                f"可信度：{item.confidence} · Meta 覆盖：{item.meta_coverage:.0f}%",
            )
        )
    lines.extend(
        (
            "",
            "竞技表现按各赛季玩家历史段位与同期 Meta 进行校正"
            if scope == "生涯"
            else "竞技表现按本赛季玩家历史段位与同期 Meta 进行校正",
            "小样本已进行可信度收缩",
            "快速模式参与使用量、个人快速基准和综合表现，但不直接与 Meta 比较",
        )
    )
    rated = [item for item in profile.signature_heroes if getattr(item, "rating", None) is not None]
    if rated and getattr(profile, "rating_version", "shadow") == "v2":
        lines.extend(("", "V2 评分摘要"))
        for item in rated:
            lines.extend(_rating_lines(item.rating))
    return "\n".join(lines)


def format_player_sickness(profile: PlayerSignatureProfile) -> str:
    analysis_scope = getattr(profile, "scope", None)
    scope = analysis_scope_label(analysis_scope)
    show_v2 = getattr(profile, "rating_version", "shadow") == "v2"
    competitive_total = int(getattr(profile, "competitive_matches", 0) or 0)
    total_matches = int(getattr(profile, "total_matches", competitive_total) or competitive_total)
    quick_total = max(0, total_matches - competitive_total)
    lines = [
        f"我的绝症｜{scope}分析",
        f"玩家：{profile.player_name}（UID：{profile.uid}）",
        f"统计范围：{scope}",
        f"总场次：{_count(total_matches)} · 竞技：{_count(competitive_total)} · 快速：{_count(quick_total)}",
        f"Meta 覆盖：{profile.meta_coverage:.0f}% · 绝症指数 = 使用指数 × 弱势表现 × 证据修正",
        "这是“玩得多但表现相对差”的娱乐型相对排名，不是医学意义上的确诊。",
        "候选范围：总场次≥10，或竞技≥5，或快速≥20；Performance ≤ -10 才进入绝症榜。",
    ]
    if show_v2:
        lines[4] = "V2 评分：Mastery / Performance / Specialization / Confidence"
        lines[6] = "候选与排序由 V2 评分分类、专精度和有效证据决定"
    if profile.partial:
        lines.append("提示：部分历史赛季或 Meta 数据不可用，以下仅展示可确认结果。")
    if not getattr(profile, "meta_available", True):
        lines.append("提示：当前缺少同期 Meta，综合表现仅基于个人竞技/快速基准，可信度已降级。")
    if profile.meta_source_timestamp:
        stale_text = "（部分使用最近缓存）" if profile.meta_stale else ""
        lines.append(
            f"Meta 来源：{profile.meta_source} · 最新上游时间：{profile.meta_source_timestamp}{stale_text}"
        )
    lines.extend(("", "绝症英雄排名 Top 10"))
    if not profile.sick_heroes:
        lines.append("目前没有可用于相对排名的候选英雄。")
        return "\n".join(lines)
    if show_v2:
        lines.extend(("", "V2 绝症英雄排名 Top 10"))
        for index, item in enumerate(profile.sick_heroes, 1):
            rating = getattr(item, "rating", None)
            if rating is None:
                lines.extend((f"{index}. {item.hero_name}", "V2 评分暂不可用"))
                continue
            lines.extend((
                f"{index}. {item.hero_name}｜使用占比：{item.usage_share:.1f}%｜竞技：{_count(item.competitive_matches)} 场",
                f"{product_status(rating)}",
                f"战术原型：{archetype_summary(rating.archetype)}",
                *_rating_lines(rating),
            ))
        return "\n".join(lines)
    for index, item in enumerate(profile.sick_heroes, 1):
        lines.extend(
            (
                f"{index}. {item.hero_name}",
                f"总计：{_count(item.total_matches)} 场 · 竞技：{_count(item.competitive_matches)} · 快速：{_count(item.quick_matches)} · 使用占比：{item.usage_share:.1f}%",
                f"竞技胜率：{_percent(item.actual_win_rate)} · 快速胜率：{_percent(item.quick_win_rate)} · 同期 Meta：{_percent(item.expected_meta_win_rate)}",
                f"个人竞技相对表现：{_delta(item.personal_competitive_delta)} · 个人快速相对表现：{_delta(item.personal_quick_delta)}",
                f"弱势表现：{item.weakness_index:.1f} · 证据修正：{item.evidence_factor:.2f} · 绝症指数：{item.sickness_score:.1f}（{sickness_severity(item.sickness_score)}）",
                f"综合表现：{item.performance_index:+.1f} · 状态：{item.status}",
                f"稳健环境差值：{_delta(item.adjusted_delta)} · 可信度：{item.confidence} · Meta 覆盖：{item.meta_coverage:.0f}%",
            )
        )
    lines.extend(
        (
            "",
            "使用指数看竞技、快速场次和使用占比；弱势表现统一来自 Performance Index 的负半轴。",
            "缺少某类数据时会按剩余信号重新分配权重；指数只用于相对排序，不代表实际损失。",
        )
    )
    if show_v2:
        rated = [item for item in profile.sick_heroes if getattr(item, "rating", None) is not None]
        if rated:
            lines.extend(("", "V2 评分明细"))
            for item in rated:
                lines.extend(_rating_lines(item.rating))
    return "\n".join(lines)


def _rating_lines(rating) -> list[str]:
    """Compact V2 block shared by text fallbacks."""
    dimensions = ("FIN", "PRS", "SUR", "TEAM", "HEAL", "FRONT", "UTIL")
    values = "｜".join(
        f"{key} {rating.dimensions.get(key.lower()):.1f}"
        if rating.dimensions.get(key.lower()) is not None else f"{key} —"
        for key in dimensions
    )
    specialization = "—" if rating.specialization is None else f"{rating.specialization:+.1f}"
    archetype = rating.archetype
    freshness_value = getattr(rating, "freshness", None)
    freshness = "—" if freshness_value is None else f"{freshness_value:.2f}"
    recent_performance = _format_rating_value(getattr(rating, "recent_performance", None))
    trend_value = getattr(rating, "trend", None)
    trend = "—" if trend_value is None else f"{trend_value:+.1f}"
    temporal_label = getattr(rating, "temporal_label", None) or "—"
    return [
        f"{temporal_label} · Freshness {freshness} · Recent Performance {recent_performance} · Trend {trend} · Recent matches {_format_rating_value(getattr(rating, 'recent_effective_matches', None))}",
        f"V2评级：{product_status(rating)}｜{archetype_summary(archetype)}",
        f"Mastery {rating.mastery:.1f}｜Performance {rating.performance:.1f}｜Specialization {specialization}",
        f"Outcome {_format_rating_value(rating.outcome)}｜Combat {_format_rating_value(rating.combat)}｜Consistency {_format_rating_value(rating.consistency)}｜Experience {rating.experience:.1f}",
        f"Combat dimensions：{values}｜Observable {rating.observable_coverage:.0f}%｜Confidence {rating.confidence:.2f}",
    ]


def _format_rating_value(value) -> str:
    return "—" if value is None else f"{value:.1f}"


__all__ = [
    "format_player_hero_analysis",
    "format_player_hero_pool_analysis",
    "format_player_environment",
    "format_player_hero_pool",
    "format_player_sickness",
    "format_player_signature",
]
