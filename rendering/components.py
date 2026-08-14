"""Reusable semantic HTML components for the visual system."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .formatters import escape_text
from .theme import STYLE


def page_shell(content: str, watermark: str = "MARVEL RIVALS") -> str:
    """Wrap a page in the shared responsive shell and footer."""

    return (
        f'<!doctype html><html><head><meta charset="utf-8">{STYLE}</head><body>'
        f'<main class="mr-page" data-watermark="{escape_text(watermark)}">'
        '<div class="mr-page__background" aria-hidden="true"></div>'
        '<div class="mr-page__slash" aria-hidden="true"></div>'
        f'<div class="mr-page__inner">{content}{footer()}</div>'
        '</main></body></html>'
    )


def page_header(
    title: str,
    subtitle: str,
    badge: str,
    *,
    title_cn: str = "",
    eyebrow: str = "MR // DATA",
    meta_items: Iterable[tuple[str, Any]] | None = None,
) -> str:
    nameplate = (
        '<div class="mr-header__nameplate">'
        f'<strong class="mr-header__title-cn">{escape_text(title_cn)}</strong>'
        '</div>'
        if title_cn else ""
    )
    if meta_items:
        meta = '<div class="mr-header__meta-grid">' + "".join(
            '<div class="mr-header__meta-item">'
            f'<span class="mr-header__meta-label">{escape_text(label)}</span>'
            f'<strong class="mr-header__meta-value">{escape_text(value)}</strong>'
            '</div>'
            for label, value in meta_items
        ) + '</div>'
    else:
        meta = f'<div class="mr-header__meta">{escape_text(subtitle)}</div>'
    return (
        '<header class="mr-header"><div class="mr-header__copy">'
        f'<div class="mr-header__eyebrow">{escape_text(eyebrow)}</div>'
        f'<h1 class="mr-header__title">{escape_text(title)}</h1>'
        f'{nameplate}'
        f'{meta}'
        f'</div><div class="mr-season">{escape_text(badge)}</div></header>'
    )


def metric_block(label: Any, value: Any) -> str:
    return (
        '<div class="mr-metric">'
        f'<span class="mr-metric__label">{escape_text(label)}</span>'
        f'<b class="mr-metric__value">{escape_text(value)}</b>'
        '</div>'
    )


def metric_grid(items: Iterable[tuple[str, Any]]) -> str:
    return '<section class="mr-metrics">' + "".join(
        metric_block(label, value) for label, value in items
    ) + "</section>"


def section_title(title: str, kicker: str = "SECTION") -> str:
    return (
        '<div class="mr-section-heading">'
        '<span class="mr-section-heading__rule" aria-hidden="true"></span>'
        f'<span class="mr-section-heading__kicker">{escape_text(kicker)}</span>'
        f'<h2 class="mr-section-heading__title">{escape_text(title)}</h2>'
        '</div>'
    )


def hero_row(index: int, title: str, summary: str, duration: str) -> str:
    return (
        '<article class="mr-hero-row">'
        f'<span class="mr-hero-row__index">{index:02d}</span>'
        '<div class="mr-hero-row__body">'
        f'<div class="mr-hero-row__title">{escape_text(title)}</div>'
        f'<div class="mr-hero-row__meta">{escape_text(summary)}</div>'
        f'<div class="mr-hero-row__meta">{escape_text(duration)}</div>'
        '</div>'
        '</article>'
    )


def match_row(
    index: int,
    result: str,
    result_class: str,
    hero: str,
    timestamp: str,
    map_name: str,
    queue: str,
    duration: str,
    kda: str,
) -> str:
    return (
        '<article class="mr-match-row">'
        f'<div class="mr-match-row__index">{index:02d}</div>'
        '<div><div class="mr-match-row__main">'
        f'<span class="mr-match-row__result mr-match-row__result--{escape_text(result_class)}">{escape_text(result)}</span>'
        f'{escape_text(hero)}</div>'
        f'<div class="mr-match-row__meta">{escape_text(timestamp)} · {escape_text(map_name)} · '
        f'{escape_text(queue)} · {escape_text(duration)}</div></div>'
        f'<div class="mr-match-row__kda">{escape_text(kda)}</div>'
        '</article>'
    )


def _team_number(camp: Any) -> str:
    try:
        return f"{int(camp):02d}"
    except (TypeError, ValueError):
        return escape_text(camp)


def team_panel(camp: Any, members: str, winner_side: Any = None) -> str:
    camp_text = escape_text(camp)
    if winner_side is None:
        state, result = "unknown", "NO RESULT"
    elif str(camp) == str(winner_side):
        state, result = "winner", "VICTORY"
    else:
        state, result = "loss", "DEFEAT"
    return (
        f'<section class="mr-team mr-team--{state}">'
        '<header class="mr-team__header"><div>'
        f'<div class="mr-team__name">TEAM {_team_number(camp)}</div>'
        f'<div class="mr-team__raw">阵营 {camp_text}</div>'
        f'</div><div class="mr-team__result">{result}</div></header>'
        f'<div class="mr-team__members">{members}</div></section>'
    )


def player_row(name: str, hero: str, stats: str, extra: str) -> str:
    return (
        '<div class="mr-player-row">'
        f'<div class="mr-player-row__name">{escape_text(name)}</div>'
        f'<div class="mr-player-row__hero">{escape_text(hero)}</div>'
        f'<div class="mr-player-row__stats">{escape_text(stats)}</div>'
        f'<div class="mr-player-row__extra">{escape_text(extra)}</div>'
        '</div>'
    )


def empty_state(message: str) -> str:
    return (
        '<section class="mr-empty">'
        '<span class="mr-empty__mark">NO DATA</span>'
        f'<span>{escape_text(message)}</span>'
        '</section>'
    )


def footer(content: str = "数据页") -> str:
    return (
        '<footer class="mr-footer">'
        '<span>漫威争锋</span>'
        f'<span>{escape_text(content)}</span>'
        '</footer>'
    )
