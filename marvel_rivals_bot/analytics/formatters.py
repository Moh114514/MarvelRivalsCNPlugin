"""Simplified-Chinese formatters for Player × Meta ViewModels."""

from __future__ import annotations

from datetime import datetime

from .models import CareerHeroSignature, PlayerHeroMetaComparison, PlayerMetaProfile, PlayerSignatureProfile


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}pp"


def _count(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


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
    scope = "—" if not profile.first_season else profile.first_season
    if profile.latest_season and profile.latest_season != profile.first_season:
        scope = f"{scope} → {profile.latest_season}"
    lines = [
        "我的绝活｜生涯综合",
        f"玩家：{profile.player_name}（UID：{profile.uid}）",
        f"统计范围：{scope}",
        f"Meta 覆盖：{profile.meta_coverage:.0f}%",
        f"生涯总场次：{_count(profile.total_matches)} · 竞技：{_count(profile.competitive_matches)}",
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
    lines.extend(("", "生涯绝活 Top 5"))
    for index, item in enumerate(profile.signature_heroes, 1):
        tags = " · ".join((item.classification, *item.tags))
        lines.extend(
            (
                f"{index}. {item.hero_name}",
                tags,
                f"总计：{_count(item.total_matches)} 场 · 竞技：{_count(item.competitive_matches)} 场",
                f"竞技胜率：{_percent(item.actual_win_rate)} · 同期 Meta：{_percent(item.expected_meta_win_rate)}",
                f"环境领先：{_delta(item.raw_delta)} · 稳健领先：{_delta(item.adjusted_delta)}",
                f"有效赛季：{item.effective_seasons} · 高于环境：{item.positive_seasons} · 稳定性：{_percent(item.stability)}",
                f"可信度：{item.confidence} · Meta 覆盖：{item.meta_coverage:.0f}%",
            )
        )
    lines.extend(
        (
            "",
            "竞技表现按各赛季玩家历史段位与同期 Meta 进行校正",
            "小样本已进行可信度收缩",
            "快速模式仅参与英雄使用量统计",
        )
    )
    return "\n".join(lines)


def format_player_sickness(profile: PlayerSignatureProfile) -> str:
    scope = "—" if not profile.first_season else profile.first_season
    if profile.latest_season and profile.latest_season != profile.first_season:
        scope = f"{scope} → {profile.latest_season}"
    lines = [
        "我的绝症",
        f"玩家：{profile.player_name}（UID：{profile.uid}）",
        f"统计范围：{scope}",
        f"竞技总场次：{_count(profile.competitive_matches)} · Meta 覆盖：{profile.meta_coverage:.0f}%",
        "候选规则：可比较竞技场次≥20、有效覆盖≥60%、稳健劣势≤-2pp、预计少赢≥1场，且不属于绝活分类。",
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
        lines.append("没有英雄同时满足场次、覆盖率和稳健劣势条件。")
        return "\n".join(lines)
    for index, item in enumerate(profile.sick_heroes, 1):
        lines.extend(
            (
                f"{index}. {item.hero_name}",
                f"竞技：{_count(item.comparable_matches)} 场 · 实际胜率：{_percent(item.actual_win_rate)} · 同期 Meta：{_percent(item.expected_meta_win_rate)}",
                f"稳健劣势：{_delta(item.adjusted_delta)} · Meta 覆盖：{item.meta_coverage:.0f}% · 同段位覆盖：{item.rank_specific_coverage:.0f}%",
                f"可信度：{item.confidence} · 预计少赢约 {item.sick_score:.1f} 场",
            )
        )
    lines.extend(
        (
            "",
            "绝症与绝活使用同一套同期 Meta 基准，两个集合互斥。",
            "预计少赢场次是统计估计，用于表达和排序，不代表实际确定损失。",
        )
    )
    return "\n".join(lines)


__all__ = [
    "format_player_environment",
    "format_player_hero_pool",
    "format_player_sickness",
    "format_player_signature",
]
