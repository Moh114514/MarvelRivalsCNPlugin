from __future__ import annotations

import re
from typing import Any

from .models import CardButton, InteractiveCard
try:
    from ..marvel_rivals_bot.services.rivals import format_season_name
except ImportError:
    from marvel_rivals_bot.services.rivals import format_season_name


def _md(value: Any) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>])", r"\\\1", str(value))


def _match_uid(data: dict) -> str:
    for key in ("matchUid", "matchUID", "id"):
        value = data.get(key)
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


def build_recent_card(uid: str, season_code: str, matches: list[dict]) -> InteractiveCard:
    lines = [f"**{_md(format_season_name(season_code))} · 选择要查看的对局**"]
    buttons = []
    for index, item in enumerate(matches[:10], 1):
        match_uid = _match_uid(item)
        if match_uid and not re.search(r"\s", match_uid):
            buttons.append(CardButton(f"第{index}场", "command", f"/对局详情 {match_uid}", "blue"))
    if not matches:
        lines += ["", "暂无可用比赛记录。"]
    rows = [buttons[index:index + 2] for index in range(0, min(len(buttons), 10), 2)]
    return InteractiveCard("\n".join(lines), rows)
