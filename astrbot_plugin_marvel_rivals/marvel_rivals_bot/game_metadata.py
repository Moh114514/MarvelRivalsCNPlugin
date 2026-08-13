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

# match_map_id -> (official CN map name, objective, queue variant).
# The queue variant describes the map ID variant; game_mode_id remains the
# authoritative source for the queue of an individual match.
MATCH_MAPS: dict[int, tuple[str, str, str | None]] = {
    # 融合模式
    1034: ("东京2099：新涩谷区", "融合模式", "quick"),
    1230: ("东京2099：新涩谷区", "融合模式", "competitive"),
    1101: ("银河帝国瓦坎达：贾利亚神殿", "融合模式", "quick"),
    1267: ("银河帝国瓦坎达：贾利亚神殿", "融合模式", "competitive"),
    1217: ("永恒之夜帝国：中央公园", "融合模式", "quick"),
    1292: ("永恒之夜帝国：中央公园", "融合模式", "competitive"),
    1240: ("克林塔：共生地表", "融合模式", "quick"),
    1290: ("克林塔：共生地表", "融合模式", "competitive"),
    2041: ("昆仑：天都之心", "融合模式", "quick"),
    2042: ("昆仑：天都之心", "融合模式", "competitive"),
    1411: ("曼哈顿下城", "融合模式", "quick"),
    1421: ("曼哈顿下城", "融合模式", "competitive"),

    # 巡航模式
    1032: ("阿斯加德：世界树", "巡航模式", "quick"),
    1231: ("阿斯加德：世界树", "巡航模式", "competitive"),
    1148: ("东京2099：蜘蛛岛", "巡航模式", "quick"),
    1245: ("东京2099：蜘蛛岛", "巡航模式", "competitive"),
    1201: ("永恒之夜帝国：中城区", "巡航模式", "quick"),
    1291: ("永恒之夜帝国：中城区", "巡航模式", "competitive"),
    1286: ("地狱火晚宴：阿拉寇", "巡航模式", "quick"),
    1311: ("地狱火晚宴：阿拉寇", "巡航模式", "competitive"),
    1413: ("沉思藏馆", "巡航模式", "quick"),
    1418: ("沉思藏馆", "巡航模式", "competitive"),
    1420: ("底比斯", "巡航模式", "quick"),
    1434: ("底比斯", "巡航模式", "competitive"),  

    # 角逐模式
    1170: ("阿斯加德：仙宫", "角逐模式", "quick"),
    1236: ("阿斯加德：仙宫", "角逐模式", "competitive"),
    1235: ("银河帝国瓦坎达：黄金之城", "角逐模式", "quick"),
    1272: ("银河帝国瓦坎达：黄金之城", "角逐模式", "competitive"),
    1287: ("九头蛇：夏提厄冰山", "角逐模式", "quick"),
    1288: ("九头蛇：夏提厄冰山", "角逐模式", "competitive"),
    1309: ("地狱火晚宴：克拉科", "角逐模式", "quick"),
    1310: ("地狱火晚宴：克拉科", "角逐模式", "competitive"),
    1317: ("克林塔：天神遗骸", "角逐模式", "quick"),
    1318: ("克林塔：天神遗骸", "角逐模式", "competitive"),

    # 已确认的特殊地图
    1118: ("永恒之夜帝国：至圣所", "纷争模式", "arcade"),
    1246: ("东京2099：二之丸", "征服模式", "arcade"),
    1254: ("阿斯加德：仙宫（杰夫冬季活动）", "杰夫冬季活动", "arcade"),
    1289: ("世界竞技场", "醒狮争霸", "arcade"),
    1307: ("克林塔：深渊王座", "资源争夺", "quick"),
    1314: ("奥创纪元", "特殊模式", "arcade"),
    1320: ("克林塔：深渊王座", "资源争夺", "competitive"),
    1399: ("天尊花园", "18对18征服（歼灭）", "arcade"),
    1408: ("杰夫乐园", "杰夫活动模式", "arcade"),
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
    metadata = MATCH_MAPS.get(map_id)
    return f"{metadata[0]}（{map_id}）" if metadata else f"未知地图（ID {map_id}）"


def get_map_mode(value: Any) -> str | None:
    map_id = _integer(value)
    metadata = MATCH_MAPS.get(map_id) if map_id is not None else None
    return metadata[1] if metadata else None


def get_map_queue_variant(value: Any) -> str | None:
    map_id = _integer(value)
    metadata = MATCH_MAPS.get(map_id) if map_id is not None else None
    return metadata[2] if metadata else None


def format_play_mode(value: Any) -> str:
    mode_id = _integer(value)
    return f"玩法编号 {mode_id}" if mode_id is not None else "玩法编号未知"
