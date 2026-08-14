"""Small HTML components shared by the rendering pages."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .formatters import escape_text
from .theme import STYLE


def page_shell(content: str) -> str:
    return f'<!doctype html><html><head><meta charset="utf-8">{STYLE}</head><body><main class="card">{content}</main></body></html>'


def page_header(title: str, subtitle: str, badge: str) -> str:
    return f'<header class="head"><div><div class="title">{title}</div><div class="sub">{subtitle}</div></div><div class="badge">{badge}</div></header>'


def metric_block(label: Any, value: Any) -> str:
    return f'<div class="metric"><span>{escape_text(label)}</span><b>{escape_text(value)}</b></div>'


def metric_grid(items: Iterable[tuple[str, Any]]) -> str:
    return '<section class="overview">' + "".join(
        metric_block(label, value) for label, value in items
    ) + "</section>"


def section_title(title: str) -> str:
    return f'<div class="team-title">{title}</div>'


def hero_row(index: int, title: str, summary: str, duration: str) -> str:
    return f'<article class="hero-row"><div class="main">{index}. {title}</div><div class="meta">{summary}</div><div class="meta">{duration}</div></article>'


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
        f'<div class="match"><div class="index">{index:02d}</div>'
        f'<div><div class="main"><span class="{result_class}">{result}</span> · {hero}</div>'
        f'<div class="meta">{timestamp} · {map_name} · {queue} · {duration}</div>'
        f'</div><div class="kda">{kda}</div></div>'
    )


def team_panel(camp: str, members: str) -> str:
    return f'<section class="team"><div class="team-title">阵营 {camp}</div>{members}</section>'


def player_row(name: str, hero: str, stats: str, extra: str) -> str:
    return f'<div class="player"><div class="name">{name}</div><div class="hero">{hero}</div><div class="stats">{stats}</div><div class="extra">{extra}</div></div>'


def empty_state(message: str) -> str:
    return f'<div class="empty">{message}</div>'


def footer(content: str = "") -> str:
    """Return an optional footer without forcing one into existing pages."""

    return f'<footer>{content}</footer>' if content else ""
