from __future__ import annotations

from typing import Any


# game_mode_id describes the matchmaking queue, not the map objective.
GAME_MODE_MAP: dict[int, str] = {
    0: "快速比赛",
    1: "快速比赛",
    2: "竞技比赛",
    3: "自定义比赛",
    6: "街机/征服",
    7: "训练/街机",
}

# Only include match_map_id values with reliable external confirmation.
SPECIAL_MAP_MAP: dict[int, str] = {
    1118: "圣所 / Sanctum Sanctorum",
    1246: "二之丸 / Ninomaru",
    1254: "皇家宫殿（杰夫冬季活动）",
    1289: "世界竞技场 / World Arena",
    1307: "克林塔：克努尔王座",
    1314: "奥创纪元 / Age of Ultron",
    1320: "克林塔：克努尔王座",
    1399: "Grand Garden",
    1408: "Jeffland",
}

SPECIAL_MAP_MODE_MAP: dict[int, str] = {
    1118: "Doom Match",
    1246: "Conquest",
    1254: "Jeff's Winter Splash Festival",
    1289: "Clash of Dancing Lions",
    1307: "Resource Rumble / Quick",
    1314: "特殊模式",
    1320: "Resource Rumble / Competitive",
    1399: "18v18 Annihilation",
    1408: "杰夫活动模式",
}

# This namespace belongs to RivalsMeta and is not used to interpret CN API fields.
RIVALSMETA_SEASON_MAP: dict[int, str] = {
    1: "S0",
    2: "S1",
    3: "S1.5",
    4: "S2",
    5: "S2.5",
    6: "S3",
    7: "S3.5",
    8: "S4",
    9: "S4.5",
    10: "S5",
    11: "S5.5",
    12: "S6",
    13: "S6.5",
    14: "S7",
    15: "S7.5",
    16: "S8",
    17: "S8.5",
    18: "S9",
}


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_game_mode(value: Any) -> str:
    mode_id = _integer(value)
    if mode_id is None:
        return "未知队列"
    name = GAME_MODE_MAP.get(mode_id)
    return f"{name}（{mode_id}）" if name else f"未知队列（gameModeId={mode_id}）"


def format_queue(game_mode: Any, play_mode: Any) -> str:
    game_mode_id = _integer(game_mode)
    play_mode_id = _integer(play_mode)
    if play_mode_id == 1 or game_mode_id == 3:
        return "自定义比赛"
    if game_mode_id == 2:
        return "竞技比赛"
    if game_mode_id in (6, 7):
        return "街机模式"
    if game_mode_id in (0, 1):
        return "快速比赛"
    return format_game_mode(game_mode)


def format_match_map(value: Any) -> str:
    map_id = _integer(value)
    if map_id is None:
        return "未知地图"
    name = SPECIAL_MAP_MAP.get(map_id)
    return f"{name}（{map_id}）" if name else f"未知地图（ID {map_id}）"


def get_map_mode(value: Any) -> str | None:
    map_id = _integer(value)
    return SPECIAL_MAP_MODE_MAP.get(map_id) if map_id is not None else None


def format_play_mode(value: Any) -> str:
    mode_id = _integer(value)
    return f"玩法编号 {mode_id}" if mode_id is not None else "玩法编号未知"
