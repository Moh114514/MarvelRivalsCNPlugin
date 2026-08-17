"""Player × Meta HTML pages built from stable analytics ViewModels."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

try:
    from ...marvel_rivals_bot.analytics.models import PlayerHeroMetaComparison, PlayerMetaProfile
except ImportError:
    from marvel_rivals_bot.analytics.models import PlayerHeroMetaComparison, PlayerMetaProfile

from ..components import empty_state, page_header, page_shell, section_title
from ..formatters import escape_text


def _value(value: Any, fallback: str = "—") -> str:
    return escape_text(fallback if value is None else value)


def _percent(value: float | None) -> str:
    return _value(None if value is None else f"{value:.1f}%")


def _delta(value: float | None) -> str:
    return _value(None if value is None else f"{value:+.1f}pp")


def _source_line(profile: PlayerMetaProfile) -> str:
    timestamp = profile.source_timestamp
    if isinstance(timestamp, datetime):
        timestamp = timestamp.astimezone().strftime("%Y-%m-%d %H:%M")
    stale = "是" if profile.stale else "否"
    notice = '<span>当前上游暂不可用，展示最近缓存数据</span>' if profile.stale else ""
    return (
        '<div class="mr-meta-source">'
        f'<span>数据来源：{_value(profile.source)}</span>'
        f'<span>上游时间：{_value(timestamp)}</span>'
        f'<span>Stale：{stale}</span>{notice}'
        '</div>'
    )


def _header(profile: PlayerMetaProfile, title: str, title_cn: str) -> str:
    return page_header(
        title,
        "玩家与全局英雄环境交叉分析",
        profile.season_label,
        title_cn=title_cn,
        eyebrow="MR // PLAYER META",
        meta_items=[
            ("当前段位", profile.cn_rank_label),
            ("Meta 段位", profile.meta_rank_label),
            ("UID", profile.uid),
        ],
    ) + _source_line(profile)


def _environment_row(index: int, result: Any, metric: str) -> str:
    value = result.matches if metric == "matches" else getattr(result, metric)
    value_text = f"{value:,}" if metric == "matches" else _percent(value)
    return (
        '<article class="mr-player-meta-row mr-player-meta-row--environment">'
        f'<span class="mr-player-meta-row__index">{index:02d}</span>'
        '<div class="mr-player-meta-row__hero">'
        f'<strong>{_value(result.hero_name)}</strong>'
        f'<span>{_value("场次 " + format(result.matches, ","))}</span>'
        '</div>'
        f'<strong class="mr-player-meta-row__value">{_value(value_text)}</strong>'
        '</article>'
    )


def _environment_section(title: str, metric: str, results: Iterable[Any]) -> str:
    rows = "".join(_environment_row(index, result, metric) for index, result in enumerate(results, 1))
    return (
        '<section class="mr-section mr-player-meta-section">'
        + section_title(title, "TOP 5")
        + (f'<div class="mr-player-meta-list">{rows}</div>' if rows else empty_state("暂无该项环境数据"))
        + '</section>'
    )


def build_player_meta_environment_html(profile: PlayerMetaProfile) -> str:
    overview = profile.environment
    content = _header(profile, "MY META", f"{profile.player_name} 的环境")
    if overview is None:
        content += empty_state("暂无可用的段位环境数据")
    else:
        content += _environment_section("胜率最高", "win_rate", overview.win_rate)
        content += _environment_section("最常见", "pick_rate", overview.pick_rate)
        content += _environment_section("最高 Ban", "ban_rate", overview.ban_rate)
    return page_shell(content, watermark="MY META")


def _comparison_row(index: int, item: PlayerHeroMetaComparison, signature: bool = False) -> str:
    delta_class = "positive" if item.win_rate_delta is None or item.win_rate_delta >= 0 else "negative"
    return (
        f'<article class="mr-player-meta-row mr-player-meta-row--comparison{(" mr-player-meta-row--signature" if signature else "")}">'  # noqa: E501
        f'<span class="mr-player-meta-row__index">{index:02d}</span>'
        '<div class="mr-player-meta-row__hero">'
        f'<strong>{_value(item.hero_name)}</strong>'
        f'<span>总计 {item.total_matches:,} 场 · 快速 {item.quick_matches:,} · 竞技 {item.ranked_matches:,}</span>'
        '</div>'
        '<div class="mr-player-meta-row__metric mr-player-meta-row__metric--personal">'
        f'<span>竞技占比</span><strong>{_percent(item.ranked_share)}</strong>'
        '</div>'
        '<div class="mr-player-meta-row__metric mr-player-meta-row__metric--meta">'
        f'<span>竞技胜率</span><strong>{_percent(item.ranked_win_rate)}</strong>'
        '</div>'
        f'<strong class="mr-player-meta-row__delta mr-player-meta-row__delta--{delta_class}">{_delta(item.win_rate_delta)}</strong>'
        '<div class="mr-player-meta-row__detail">'
        f'<span>Meta {_percent(item.meta_win_rate)}</span>'
        f'<span>选取率 {_percent(item.meta_pick_rate)}</span>'
        f'<span>Ban率 {_percent(item.meta_ban_rate)}</span>'
        '</div>'
        '</article>'
    )


def _comparison_page(
    profile: PlayerMetaProfile,
    title: str,
    title_cn: str,
    items: Iterable[PlayerHeroMetaComparison],
    section: str,
    kicker: str,
    *,
    signature: bool = False,
    empty: str,
) -> str:
    rows = "".join(_comparison_row(index, item, signature) for index, item in enumerate(items, 1))
    content = _header(profile, title, title_cn)
    content += '<section class="mr-section mr-player-meta-section">'
    content += section_title(section, kicker)
    content += f'<div class="mr-player-meta-list mr-player-meta-list--comparison">{rows}</div>' if rows else empty_state(empty)
    content += '</section>'
    return page_shell(content, watermark=title)


def build_player_hero_pool_html(profile: PlayerMetaProfile) -> str:
    return _comparison_page(
        profile,
        "MY HERO POOL",
        f"{profile.player_name} 的英雄池",
        profile.hero_pool,
        "个人数据 × 同段位环境",
        "PLAYER HERO POOL",
        empty="暂无可用于比较的个人英雄数据",
    )


def build_player_signature_html(profile: PlayerMetaProfile) -> str:
    return _comparison_page(
        profile,
        "MY SPECIALTY",
        f"{profile.player_name} 的绝活",
        profile.signature_heroes,
        f"总场次 ≥ {profile.minimum_matches} · 竞技场次 ≥ {profile.minimum_ranked_matches} · 胜率高于 Meta",
        "PLAYER SPECIALTY",
        signature=True,
        empty="暂无同时满足总场次、竞技场次和胜率要求的英雄",
    )


__all__ = [
    "build_player_hero_pool_html",
    "build_player_meta_environment_html",
    "build_player_signature_html",
]
