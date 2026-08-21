from __future__ import annotations

import re
from typing import Any

from .models import CardButton, InteractiveCard
try:
    from ..marvel_rivals_bot.reference.seasons import format_season_name
except ImportError:
    from marvel_rivals_bot.reference.seasons import format_season_name


def _md(value: Any) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>])", r"\\\1", str(value))


def _match_uid(data: Any) -> str:
    typed_uid = getattr(data, "match_uid", None)
    if typed_uid not in (None, "") and str(typed_uid).strip():
        return str(typed_uid).strip()
    getter = getattr(data, "get", None)
    if not callable(getter):
        return ""
    for key in ("matchUid", "matchUID", "match_uid", "id"):
        value = getter(key)
        if value not in (None, "") and str(value).strip():
            return str(value).strip()
    return ""


def build_capability_test_card() -> InteractiveCard:
    return InteractiveCard(
        markdown=(
            "# 漫威争锋查询\n"
            "这是 QQ 官方机器人富消息能力测试。\n\n"
            "如果你能看到本段 Markdown 和下方两个按钮，说明原生富消息已启用。"
        ),
        rows=[[
            CardButton("查询战绩", "command", "/战绩 1287101468", "blue"),
            CardButton(
                "打开项目",
                "url",
                "https://github.com/Moh114514/MarvelRivalsCNPlugin",
            ),
        ]],
    )


def _build_match_selection_card(
    title: str,
    matches: list[Any],
    *,
    limit: int,
    buttons_per_row: int,
    session_minutes: int | None = None,
) -> InteractiveCard:
    total = len(matches)
    lines = [f"**{_md(title)} · 选择要查看的对局**"]
    if session_minutes is not None and total:
        lines.append(f"共 {total} 场；列表编号会话有效 {session_minutes} 分钟。")
    buttons = []
    for index, item in enumerate(matches[:limit], 1):
        match_uid = _match_uid(item)
        if match_uid and not re.search(r"\s", match_uid):
            buttons.append(CardButton(f"第{index}场", "command", f"/对局详情 {match_uid}", "blue"))
    if not matches:
        lines += ["", "暂无可用比赛记录。"]
    elif total > limit:
        lines.append(f"卡片展示前 {limit} 场；完整范围请在有效期内回复 /对局 1 ~ /对局 {total}。")
    rows = [buttons[index:index + buttons_per_row] for index in range(0, len(buttons), buttons_per_row)]
    return InteractiveCard("\n".join(lines), rows)


def build_recent_card(uid: str, season_code: str, matches: list[dict]) -> InteractiveCard:
    return _build_match_selection_card(
        format_season_name(season_code), matches,
        limit=10, buttons_per_row=2,
    )


def build_match_window_card(
    window_label: str,
    matches: list[Any],
    session_minutes: int = 10,
) -> InteractiveCard:
    """Build the selectable detail card for a time-window report."""

    return _build_match_selection_card(
        window_label, matches,
        limit=25, buttons_per_row=5,
        session_minutes=max(1, int(session_minutes)),
    )
