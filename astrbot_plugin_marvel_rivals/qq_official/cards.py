from __future__ import annotations

import re
from typing import Any

from .models import CardButton, InteractiveCard

try:
    from ..marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from ..marvel_rivals_bot.hero_names import format_hero_name, get_hero_name
    from ..marvel_rivals_bot.models import HeroQueryResult, PlayerStats
    from ..marvel_rivals_bot.services.rivals import format_season_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from marvel_rivals_bot.hero_names import format_hero_name, get_hero_name
    from marvel_rivals_bot.models import HeroQueryResult, PlayerStats
    from marvel_rivals_bot.services.rivals import format_season_name


def _md(value: Any) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>])", r"\\\1", str(value))


def _number(value: Any, fallback: str = "-") -> str:
    if not isinstance(value, (int, float)):
        return fallback
    return f"{value:.1f}" if isinstance(value, float) and not value.is_integer() else str(int(value))


def _count(data: dict, *keys: str) -> str:
    for key in keys:
        if key in data:
            return _number(data[key])
    return "-"


def _season_command(season: str) -> str:
    name = format_season_name(season)
    return "S0" if name == "S0" else name.replace("上半赛季", "").replace("下半赛季", ".5")


def _first_match(payload: dict) -> dict:
    data = payload.get("data", payload)
    matches = data.get("matches", []) if isinstance(data, dict) else []
    return matches[0] if isinstance(matches, list) and matches and isinstance(matches[0], dict) else {}


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


def build_player_card(stats: PlayerStats) -> InteractiveCard:
    profile, summary = stats.profile, stats.summary
    season = _season_command(stats.season)
    lines = [
        "# 漫威争锋 · 国服战绩",
        f"## {_md(profile.name)}",
        f"UID `{_md(profile.uid)}` · Lv\\.{_md(profile.level if profile.level is not None else '-')}",
        "",
        f"**{_md(format_season_name(stats.season))} · {_md(profile.rank_game_season or '暂无段位')}**",
        "",
        f"场次 **{_number(summary.matches)}**　胜场 **{_number(summary.wins)}**　胜率 **{_number(summary.win_rate)}%**",
        f"K / D / A　**{_number(summary.kills)} / {_number(summary.deaths)} / {_number(summary.assists)}**",
    ]
    if stats.heroes:
        lines += ["", "### 常用英雄"]
        for index, hero in enumerate(stats.heroes[:5], 1):
            lines.append(
                f"{index}\\. **{_md(hero.hero_name)}**　{_number(hero.matches)} 场 / "
                f"{_number(hero.wins)} 胜 / {_number(hero.kills)} 击败"
            )
    rows = [[
        CardButton("最近10场", "command", f"/最近对局 {profile.uid} {season}", "blue"),
        CardButton("刷新战绩", "command", f"/战绩 {profile.uid} {season}"),
    ]]
    hero_names = [get_hero_name(hero.hero_id) for hero in stats.heroes[:3]]
    hero_buttons = [
        CardButton(name, "command", f"/英雄数据 {name} {profile.uid} {season}")
        for name in hero_names
        if name != "未知英雄" and not name.startswith("英雄 ")
    ]
    if hero_buttons:
        rows.append(hero_buttons)
    return InteractiveCard("\n".join(lines), rows)


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


def build_hero_card(result: HeroQueryResult) -> InteractiveCard:
    data = result.payload.get("data", result.payload)
    careers = data.get("careers", []) if isinstance(data, dict) else []
    hero = careers[0] if isinstance(careers, list) and careers and isinstance(careers[0], dict) else {}
    matches = hero.get("totalMatchCount")
    wins = hero.get("totalMatchWinCount")
    win_rate = wins * 100 / matches if isinstance(matches, (int, float)) and matches and isinstance(wins, (int, float)) else None
    season = _season_command(result.season)
    lines = [
        f"# {_md(format_hero_name(result.hero_id, result.hero_name))} · {_md(format_season_name(result.season))}",
        f"UID `{_md(result.uid)}`",
        "",
        f"比赛 **{_number(matches)}**　胜场 **{_number(wins)}**　胜率 **{_number(win_rate)}%**",
        f"K / D / A　**{_count(hero, 'k')}/{_count(hero, 'd')}/{_count(hero, 'a')}**",
        "",
        f"英雄伤害 **{_count(hero, 'totalHeroDamage')}**　治疗 **{_count(hero, 'totalHeroHeal')}**",
        f"承受伤害 **{_count(hero, 'totalDamageTaken')}**",
        f"MVP **{_count(hero, 'totalMvpTimes')}**　SVP **{_count(hero, 'totalSvpTimes')}**",
    ]
    if not hero:
        lines += ["", "暂无该英雄的生涯数据。"]
    return InteractiveCard("\n".join(lines), [[
        CardButton("刷新英雄", "command", f"/英雄数据 {result.hero_name} {result.uid} {season}", "blue"),
        CardButton("玩家战绩", "command", f"/战绩 {result.uid} {season}"),
        CardButton("最近对局", "command", f"/最近对局 {result.uid} {season}"),
    ]])


def build_match_card(payload: dict) -> InteractiveCard:
    match = _first_match(payload)
    match_uid = _match_uid(match)
    lines = ["**对局详情操作**" if match else "暂无对局数据。"]
    rows = [[CardButton("刷新详情", "command", f"/对局详情 {match_uid}", "blue")]] if match_uid else []
    return InteractiveCard("\n".join(lines), rows)
