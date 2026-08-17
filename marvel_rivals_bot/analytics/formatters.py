"""Simplified-Chinese formatters for Player × Meta ViewModels."""

from __future__ import annotations

from datetime import datetime

from .models import PlayerHeroMetaComparison, PlayerMetaProfile


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}pp"


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
        f"总场次：{item.total_matches} · 快速：{item.quick_matches} · 竞技：{item.ranked_matches}",
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


__all__ = [
    "format_player_environment",
    "format_player_hero_pool",
    "format_player_signature",
]
