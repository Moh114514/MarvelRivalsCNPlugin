"""Simplified-Chinese formatters for Player × Meta ViewModels."""

from __future__ import annotations

from datetime import datetime

from .models import CareerHeroSignature, PlayerHeroMetaComparison, PlayerMetaProfile, PlayerSignatureProfile
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
        return "—" if value is None or not matches else f"{value / matches:.1f}"
    return [
        title,
        f"场次：{_count(matches)}｜胜率：{_percent(getattr(mode, 'win_rate', None))}",
        "击败 / 最后一击 / 死亡 / 助攻："
        f"{_count(getattr(mode, 'kills', None))} / { _count(getattr(mode, 'final_hits', None))} / "
        f"{_count(getattr(mode, 'deaths', None))} / {_count(getattr(mode, 'assists', None))}",
        f"场均伤害 / 治疗 / 承伤：{average('hero_damage')} / {average('heal')} / {average('damage_taken')}",
        f"游戏时长：{_hours(getattr(mode, 'play_time', None))}｜MVP：{_count(getattr(mode, 'mvp', None))}｜SVP：{_count(getattr(mode, 'svp', None))}",
    ]


def format_player_hero_analysis(profile: PlayerSignatureProfile, hero: CareerHeroSignature) -> str:
    """Render one hero from the same ViewModel consumed by list commands."""

    scope = profile.scope
    scope_label = "生涯" if scope.kind == "career" else scope.season_code
    performance = float(hero.performance_index or 0.0)
    if hero.signature_score > 0:
        conclusion = "强势绝活"
        explanation = "这是你长期表现明显高于自身及同期环境的英雄。"
    elif hero.sickness_score > 0:
        conclusion = "高使用量相对弱势"
        explanation = "你经常使用它，但相对同期环境和自己的同模式基准表现偏低。"
    else:
        conclusion = "潜力 / 常用英雄"
        explanation = "当前数据尚不足以把它归入强势绝活或高使用量弱势。"
    lines = [
        f"{hero.hero_name} · {scope_label}分析",
        f"玩家：{profile.player_name}（UID：{profile.uid}）",
        "",
        conclusion,
        explanation,
        f"绝活指数：{hero.signature_score:.1f}｜绝症指数：{hero.sickness_score:.1f}",
        f"综合表现：{performance:+.1f}｜使用指数：{hero.play_index:.1f}｜可信度：{hero.confidence}",
        "",
        "生涯使用",
        f"总场次：{_count(hero.total_matches)}｜竞技：{_count(hero.competitive_matches)}｜快速：{_count(hero.quick_matches)}",
        f"活跃赛季：{hero.active_seasons}",
        "",
        "竞技环境比较",
        f"个人竞技胜率：{_percent(hero.actual_win_rate)}｜同期同段位 Meta：{_percent(hero.expected_meta_win_rate)}",
        f"Meta 表现：{_delta(hero.adjusted_meta_delta if hero.adjusted_meta_delta is not None else hero.adjusted_delta)}",
        f"个人竞技相对表现：{_delta(hero.personal_competitive_delta)}",
        f"个人快速相对表现：{_delta(hero.personal_quick_delta)}",
        "",
    ]
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
    scope = (
        "生涯"
        if analysis_scope is not None and analysis_scope.kind == "career"
        else (analysis_scope.season_code if analysis_scope is not None else ("—" if not profile.first_season else profile.first_season))
    )
    if analysis_scope is None and profile.latest_season and profile.latest_season != profile.first_season:
        scope = f"{scope} → {profile.latest_season}"
    lines = [
        f"我的绝活｜{scope}分析",
        f"玩家：{profile.player_name}（UID：{profile.uid}）",
        f"统计范围：{scope}",
        f"Meta 覆盖：{profile.meta_coverage:.0f}%",
        f"{scope}总场次：{_count(profile.total_matches)} · 竞技：{_count(profile.competitive_matches)}",
    ]
    if profile.partial:
        lines.append("提示：部分历史赛季未能获取，以下为可用数据的阶段性结果")
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
            lines.extend(("", "暂未形成数据上明确的长期绝活，以下为最接近的英雄。"))
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
                f"环境领先：{_delta(item.raw_delta)} · 稳健领先：{_delta(item.adjusted_delta)}",
                f"综合表现：{item.performance_index:+.1f} · 使用指数：{item.play_index:.1f} · 绝活指数：{item.signature_score:.1f}",
                f"有效赛季：{item.effective_seasons} · 高于环境：{item.positive_seasons} · 稳定性：{_percent(item.stability)}",
                f"可信度：{item.confidence} · Meta 覆盖：{item.meta_coverage:.0f}%",
            )
        )
    lines.extend(
        (
            "",
            "竞技表现按各赛季玩家历史段位与同期 Meta 进行校正",
            "小样本已进行可信度收缩",
            "快速模式参与使用量、个人快速基准和综合表现，但不直接与 Meta 比较",
        )
    )
    return "\n".join(lines)


def format_player_sickness(profile: PlayerSignatureProfile) -> str:
    analysis_scope = getattr(profile, "scope", None)
    scope = (
        "生涯"
        if analysis_scope is not None and analysis_scope.kind == "career"
        else (analysis_scope.season_code if analysis_scope is not None else ("—" if not profile.first_season else profile.first_season))
    )
    if analysis_scope is None and profile.latest_season and profile.latest_season != profile.first_season:
        scope = f"{scope} → {profile.latest_season}"
    competitive_total = int(getattr(profile, "competitive_matches", 0) or 0)
    total_matches = int(getattr(profile, "total_matches", competitive_total) or competitive_total)
    quick_total = max(0, total_matches - competitive_total)
    lines = [
        f"我的绝症｜{scope}分析",
        f"玩家：{profile.player_name}（UID：{profile.uid}）",
        f"统计范围：{scope}",
        f"总场次：{_count(total_matches)} · 竞技：{_count(competitive_total)} · 快速：{_count(quick_total)}",
        f"Meta 覆盖：{profile.meta_coverage:.0f}% · 绝症指数 = 爱玩指数 × 菜度指数 ÷ 100",
        "这是“玩得多但表现相对差”的娱乐型相对排名，不是医学意义上的确诊。",
        "候选范围：总场次≥10，或竞技≥5，或快速≥20；至少一个模式有胜率数据。明显高于同期 Meta 的英雄会被保护，不进入绝症榜。",
    ]
    if profile.partial:
        lines.append("提示：部分历史赛季或 Meta 数据不可用，以下仅展示可确认结果。")
    if profile.meta_source_timestamp:
        stale_text = "（部分使用最近缓存）" if profile.meta_stale else ""
        lines.append(
            f"Meta 来源：{profile.meta_source} · 最新上游时间：{profile.meta_source_timestamp}{stale_text}"
        )
    lines.extend(("", "绝症英雄排名 Top 10"))
    if not profile.sick_heroes:
        lines.append("目前没有可用于相对排名的候选英雄。")
        return "\n".join(lines)
    for index, item in enumerate(profile.sick_heroes, 1):
        lines.extend(
            (
                f"{index}. {item.hero_name}",
                f"总计：{_count(item.total_matches)} 场 · 竞技：{_count(item.competitive_matches)} · 快速：{_count(item.quick_matches)} · 使用占比：{item.usage_share:.1f}%",
                f"竞技胜率：{_percent(item.actual_win_rate)} · 快速胜率：{_percent(item.quick_win_rate)} · 同期 Meta：{_percent(item.expected_meta_win_rate)}",
                f"Meta 劣势：{_delta(item.meta_disadvantage)} · 个人竞技劣势：{_delta(item.personal_competitive_disadvantage)} · 个人快速劣势：{_delta(item.personal_quick_disadvantage)}",
                f"爱玩指数：{item.play_index:.1f} · 菜度指数：{item.weakness_index:.1f} · 绝症指数：{item.sick_score:.1f}（{sickness_severity(item.sick_score)}）",
                f"综合表现：{item.performance_index:+.1f} · 统一绝症指数：{item.sickness_score:.1f}",
                f"稳健环境差值：{_delta(item.adjusted_delta)} · 可信度：{item.confidence} · Meta 覆盖：{item.meta_coverage:.0f}%",
            )
        )
    lines.extend(
        (
            "",
            "爱玩指数看竞技、快速场次和使用占比；菜度指数看可用的 Meta、个人竞技、个人快速劣势。",
            "缺少某类数据时会按剩余信号重新分配权重；指数只用于相对排序，不代表实际损失。",
        )
    )
    return "\n".join(lines)


__all__ = [
    "format_player_hero_analysis",
    "format_player_environment",
    "format_player_hero_pool",
    "format_player_sickness",
    "format_player_signature",
]
