"""Run a reproducible Shadow/V2 player-rating comparison report.

The script deliberately uses the existing CN, Meta, and career-analysis
services. It writes only the requested report files; it never changes the
binding database and never saves upstream raw responses.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Running ``python tools/...py`` puts ``tools`` on sys.path, not the plugin
# root. Keep the script directly executable from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from marvel_rivals_bot.analytics.models import CareerHeroSignature, PlayerSignatureProfile
from marvel_rivals_bot.analytics.signature import PlayerCareerAnalysisService
from marvel_rivals_bot.cli import load_env_file
from marvel_rivals_bot.datasource.cn import CNDataSource
from marvel_rivals_bot.meta.service import MetaService
from marvel_rivals_bot.meta.sources.rivalsmeta import RivalsMetaSource
from marvel_rivals_bot.services.rivals import RivalsService


DEFAULT_UIDS = (
    "1000812557 1287101468 1343935371 1667187201 195963667 345168653 "
    "549948923 578402658 618837491 73942760 749299235 888217685 "
    "69977505 73942760 173465989 237259420 262007444 304077864 "
    "322075301 420576600 442046737 468147887 471345964 483757488 "
    "506221921 534970875 580147639 614417195 725230370 728331500 "
    "740243874 750738160 773940446 782368283 819877616 835571704 "
    "856361551 888217685 896986537 905915143 929185122 966201750 "
    "1014350659 1116619277 1343935371 1385470254 1412220763 "
    "1426574764 1439168944 1484360309 1502154657 1535563497 "
    "1559413367 1575949514 1580383772 1605493081 1632306808 "
    "1643447890 1757081032 1781237135 1789963872 1808904926 "
    "1896849070 195963667 1996365704 2010898130 2057134463 "
    "2075558340 2121498136"
).split()


def _parse_uids(values: list[str] | None, uid_file: str | None) -> list[str]:
    raw: list[str] = []
    if values:
        raw.extend(values)
    elif uid_file:
        raw.extend(Path(uid_file).read_text(encoding="utf-8").replace(",", " ").split())
    else:
        raw.extend(DEFAULT_UIDS)
    result: list[str] = []
    seen: set[str] = set()
    for value in raw:
        uid = str(value).strip()
        if not uid or not uid.isdigit() or uid in seen:
            continue
        seen.add(uid)
        result.append(uid)
    if not result:
        raise ValueError("没有可用的数字 UID")
    return result


def _float(value: Any, digits: int = 2) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _hero_record(hero: CareerHeroSignature) -> dict[str, Any]:
    rating = hero.rating
    return {
        "hero_id": str(hero.hero_id),
        "hero_name": hero.hero_name,
        "total_matches": hero.total_matches,
        "quick_matches": hero.quick_matches,
        "competitive_matches": hero.competitive_matches,
        "classification": hero.classification,
        "performance_index": _float(hero.performance_index),
        "signature_score": _float(hero.signature_score),
        "sickness_score": _float(hero.sickness_score),
        "rating": rating.to_dict() if rating is not None else None,
    }


def _profile_record(profile: PlayerSignatureProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "uid": profile.uid,
        "player_name": profile.player_name,
        "partial": profile.partial,
        "failed_seasons": list(profile.failed_seasons),
        "analyzed_seasons": list(profile.analyzed_seasons),
        "total_matches": profile.total_matches,
        "competitive_matches": profile.competitive_matches,
        "meta_coverage": _float(profile.meta_coverage),
        "meta_available": profile.meta_available,
        "meta_source": profile.meta_source,
        "meta_source_timestamp": profile.meta_source_timestamp,
        "meta_stale": profile.meta_stale,
        "rating_version": profile.rating_version,
        "heroes": [_hero_record(hero) for hero in profile.heroes],
        "signature_top5": [_hero_record(hero) for hero in profile.signature_heroes],
        "sickness_top10": [_hero_record(hero) for hero in profile.sick_heroes],
    }


def _hero_map(profile: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not profile:
        return {}
    return {str(hero["hero_id"]): hero for hero in profile.get("heroes", [])}


def _ids(profile: dict[str, Any] | None, field: str) -> list[str]:
    if not profile:
        return []
    return [str(item["hero_id"]) for item in profile.get(field, [])]


def _comparison(shadow: dict[str, Any] | None, v2: dict[str, Any] | None) -> dict[str, Any]:
    shadow_heroes = _hero_map(shadow)
    v2_heroes = _hero_map(v2)
    shared = sorted(set(shadow_heroes) & set(v2_heroes), key=lambda hero_id: int(hero_id))
    added = sorted(set(v2_heroes) - set(shadow_heroes), key=lambda hero_id: int(hero_id))
    removed = sorted(set(shadow_heroes) - set(v2_heroes), key=lambda hero_id: int(hero_id))
    classification_changes = []
    for hero_id in shared:
        old = shadow_heroes[hero_id]["classification"]
        new = (v2_heroes[hero_id].get("rating") or {}).get("classification")
        if old != new:
            classification_changes.append(
                {
                    "hero_id": hero_id,
                    "hero_name": v2_heroes[hero_id]["hero_name"],
                    "shadow": old,
                    "v2": new,
                }
            )

    shadow_signature = set(_ids(shadow, "signature_top5"))
    v2_signature = set(_ids(v2, "signature_top5"))
    shadow_sickness = set(_ids(shadow, "sickness_top10"))
    v2_sickness = set(_ids(v2, "sickness_top10"))

    def _set_diff(left: set[str], right: set[str]) -> dict[str, list[str]]:
        return {
            "same": sorted(left & right, key=lambda hero_id: int(hero_id)),
            "added": sorted(right - left, key=lambda hero_id: int(hero_id)),
            "removed": sorted(left - right, key=lambda hero_id: int(hero_id)),
        }

    return {
        "same_heroes": shared,
        "new_heroes_in_v2": added,
        "removed_heroes_in_v2": removed,
        "classification_changes": classification_changes,
        "signature_top5": _set_diff(shadow_signature, v2_signature),
        "sickness_top10": _set_diff(shadow_sickness, v2_sickness),
    }


def _safe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("`", "\\`").replace("\n", " ")


def _display(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return _safe(value)


def _rating_field(hero: dict[str, Any], field: str) -> Any:
    return (hero.get("rating") or {}).get(field)


def _archetype_text(hero: dict[str, Any]) -> str | None:
    archetype = _rating_field(hero, "archetype")
    if not isinstance(archetype, dict):
        return None
    primary = archetype.get("primary_style")
    secondary = archetype.get("secondary_style")
    function = archetype.get("function")
    profile = archetype.get("metric_profile")
    styles = "/".join(str(item) for item in (primary, secondary) if item)
    return f"{styles} · {function} · {profile}" if styles else f"{function} · {profile}"


def _hero_block(hero_id: str, shadow: dict[str, Any] | None, v2: dict[str, Any] | None) -> list[str]:
    hero = v2 or shadow or {"hero_id": hero_id, "hero_name": "未知英雄"}
    lines = [f"### 英雄：{_safe(hero.get('hero_name', '未知英雄'))} (`{hero_id}`)", ""]
    lines.extend([
        "#### Shadow", "",
        f"- classification: {_display(shadow.get('classification') if shadow else None)}",
        f"- performance_index: {_display(shadow.get('performance_index') if shadow else None)}",
        f"- signature_score: {_display(shadow.get('signature_score') if shadow else None)}",
    ])
    lines.extend([
        "", "#### V2", "",
        f"- archetype: {_display(_archetype_text(v2) if v2 else None)}",
        f"- baseline_group: {_display(_rating_field(v2, 'baseline_group') if v2 else None)}",
        f"- Outcome: {_display(_rating_field(v2, 'outcome') if v2 else None)}",
        f"- Combat: {_display(_rating_field(v2, 'combat') if v2 else None)}",
        f"- Consistency: {_display(_rating_field(v2, 'consistency') if v2 else None)}",
        f"- Experience: {_display(_rating_field(v2, 'experience') if v2 else None)}",
    ])
    for dimension in ("fin", "prs", "sur", "team", "heal", "front"):
        lines.append(f"- {dimension.upper()}: {_display((_rating_field(v2, 'dimensions') or {}).get(dimension) if v2 else None)}")
    for field in ("performance_raw", "performance", "mastery", "specialization", "confidence"):
        lines.append(f"- {field}: {_display(_rating_field(v2, field) if v2 else None)}")
    lines.extend([
        "", "#### 最终 Classification", "",
        f"- Shadow: {_display(shadow.get('classification') if shadow else None)}",
        f"- V2: {_display(_rating_field(v2, 'classification') if v2 else None)}",
        "",
    ])
    return lines


def _top_table(title: str, heroes: list[dict[str, Any]], *, version: str, score: str) -> list[str]:
    lines = [f"#### {title}", "", "| # | 英雄 | UID | Classification | Score | Performance | 场次 |", "|---:|---|---:|---|---:|---:|---:|"]
    if not heroes:
        lines.append("| — | — | — | — | — | — | — |")
        return lines + [""]
    for index, hero in enumerate(heroes, 1):
        if version == "v2":
            classification = _rating_field(hero, "classification")
            score_value = _rating_field(hero, "mastery") if score == "signature" else 50 - float(_rating_field(hero, "performance") or 50)
            performance = _rating_field(hero, "performance")
        else:
            classification = hero.get("classification")
            score_value = hero.get("signature_score") if score == "signature" else hero.get("sickness_score")
            performance = hero.get("performance_index")
        lines.append(
            f"| {index} | {_safe(hero.get('hero_name'))} | {hero.get('hero_id')} | {_display(classification)} | "
            f"{_display(_float(score_value))} | {_display(_float(performance))} | {hero.get('total_matches', 0)} |"
        )
    return lines + [""]


def _hero_names(ids: list[str], shadow: dict[str, Any] | None, v2: dict[str, Any] | None) -> str:
    mapping = {**_hero_map(shadow), **_hero_map(v2)}
    return "、".join(f"{mapping[item]['hero_name']}({item})" for item in ids if item in mapping) or "无"


def _comparison_block(comparison: dict[str, Any], shadow: dict[str, Any] | None, v2: dict[str, Any] | None) -> list[str]:
    lines = ["#### 绝活 Top5 集合对照", "", f"- 相同英雄：{_hero_names(comparison['signature_top5']['same'], shadow, v2)}", f"- 新增英雄（V2）：{_hero_names(comparison['signature_top5']['added'], shadow, v2)}", f"- 移除英雄（V2）：{_hero_names(comparison['signature_top5']['removed'], shadow, v2)}", "", "#### 绝症 Top10 集合对照", "", f"- 相同英雄：{_hero_names(comparison['sickness_top10']['same'], shadow, v2)}", f"- 新增英雄（V2）：{_hero_names(comparison['sickness_top10']['added'], shadow, v2)}", f"- 移除英雄（V2）：{_hero_names(comparison['sickness_top10']['removed'], shadow, v2)}", "", "#### 全部共同英雄", "", f"- 相同英雄：{_hero_names(comparison['same_heroes'], shadow, v2)}", f"- 新增英雄（V2）：{_hero_names(comparison['new_heroes_in_v2'], shadow, v2)}", f"- 移除英雄（V2）：{_hero_names(comparison['removed_heroes_in_v2'], shadow, v2)}", "", "#### 等级变化", ""]
    changes = comparison["classification_changes"]
    if not changes:
        lines.append("- 无分类变化")
    else:
        lines.extend(["| 英雄 | Shadow | V2 |", "|---|---|---|"])
        for item in changes:
            lines.append(f"| {_safe(item['hero_name'])} (`{item['hero_id']}`) | {_display(item['shadow'])} | {_display(item['v2'])} |")
    return lines + [""]


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Player Rating Shadow/V2 Validation Report", "",
        f"- 生成时间（UTC）：{report['generated_at']}",
        f"- 输入 UID：{report['input_uid_count']} 个（原始输入 {report['raw_uid_count']} 个，重复项已去重）",
        f"- 成功：{report['success_count']}，部分成功：{report['partial_count']}，失败：{report['failure_count']}",
        f"- 报告口径：{report['scope']}；Shadow 与 V2 使用同一批 UID、同一数据源与同一生涯分析范围。",
        "- 本报告不包含原始接口响应、Token、Cookie 或 QQ 绑定信息。", "",
        "## 汇总", "", "| UID | 玩家名称 | 状态 | Shadow Top5 | V2 Top5 | 分类变化 |", "|---:|---|---|---:|---:|---:|",
    ]
    for player in report["players"]:
        comparison = player.get("comparison") or {}
        shadow = player.get("shadow") or {}
        v2 = player.get("v2") or {}
        lines.append(
            f"| {player['uid']} | {_safe(player.get('player_name', '未知'))} | {_display(player['status'])} | "
            f"{len(shadow.get('signature_top5', []))} | {len(v2.get('signature_top5', []))} | "
            f"{len(comparison.get('classification_changes', []))} |"
        )
    lines.append("")
    for player in report["players"]:
        lines.extend([f"## 玩家：{_safe(player.get('player_name', '未知'))} (`{player['uid']}`)", ""])
        if player.get("errors"):
            lines.extend(["### 执行状态", ""])
            for error in player["errors"]:
                lines.append(f"- {error['version']}: {error['type']}：{_safe(error['message'])}")
            lines.append("")
        shadow = player.get("shadow")
        v2 = player.get("v2")
        for profile in (shadow, v2):
            if profile:
                version = "Shadow" if profile is shadow else "V2"
                lines.extend([
                    f"- {version} 分析赛季：{_safe(', '.join(profile.get('analyzed_seasons', [])) or '无')}",
                    f"- 总场次：{profile.get('total_matches', 0)}；竞技场次：{profile.get('competitive_matches', 0)}；Meta 覆盖：{_display(profile.get('meta_coverage'))}",
                    f"- Meta：{_display(profile.get('meta_source'))}；时间戳：{_display(profile.get('meta_source_timestamp'))}；stale：{profile.get('meta_stale', False)}",
                ])
        lines.append("")
        lines.extend(_top_table("Shadow 绝活 Top5", (shadow or {}).get("signature_top5", []), version="shadow", score="signature"))
        lines.extend(_top_table("V2 绝活 Top5", (v2 or {}).get("signature_top5", []), version="v2", score="signature"))
        lines.extend(_top_table("Shadow 绝症 Top10", (shadow or {}).get("sickness_top10", []), version="shadow", score="sickness"))
        lines.extend(_top_table("V2 绝症 Top10", (v2 or {}).get("sickness_top10", []), version="v2", score="sickness"))
        comparison = player.get("comparison")
        if comparison:
            lines.extend(_comparison_block(comparison, shadow, v2))
            shadow_map = _hero_map(shadow)
            v2_map = _hero_map(v2)
            for hero_id in sorted(set(shadow_map) | set(v2_map), key=lambda value: int(value)):
                lines.extend(_hero_block(hero_id, shadow_map.get(hero_id), v2_map.get(hero_id)))
        else:
            lines.extend(["### 英雄级对照", "", "无可比较的 Shadow/V2 英雄数据。", ""])
    return "\n".join(lines).rstrip() + "\n"


async def _build_report(args: argparse.Namespace) -> dict[str, Any]:
    uids = _parse_uids(args.uids, args.uid_file)
    config = dict(os.environ)
    if args.env_file:
        config.update(load_env_file(args.env_file))

    cache_root = Path(args.cache_root) if args.cache_root else None
    source = CNDataSource(env=config)
    rivals = RivalsService(
        source,
        cache_seconds=float(config.get("MRCN_CACHE_SECONDS", "60")),
        hero_batch_size=int(config.get("MRCN_SIGNATURE_HERO_BATCH_SIZE", "32")),
        hero_max_concurrency=int(config.get("MRCN_SIGNATURE_MAX_CONCURRENCY", "4")),
        max_inflight_requests=int(config.get("MRCN_MAX_INFLIGHT_REQUESTS", "8")),
    )
    meta_source: RivalsMetaSource | None = None
    meta_service: MetaService | None = None
    meta_enabled = str(config.get("MRCN_META_ENABLED", "true")).lower() not in {"0", "false", "no", "off"}
    if meta_enabled:
        meta_source = RivalsMetaSource(env=config)
        if cache_root is not None:
            meta_service = MetaService(
                meta_source,
                cache_root=cache_root,
                fresh_seconds=float(config.get("MRCN_META_CACHE_SECONDS", "600")),
                stale_seconds=float(config.get("MRCN_META_STALE_SECONDS", "86400")),
                default_season=str(config.get("MRCN_DEFAULT_SEASON", "19")),
                request_semaphore=rivals.request_semaphore,
            )
        else:
            meta_service = MetaService(meta_source, cache_root=Path("data"))

    common = {
        "cache_root": cache_root,
        "hero_batch_size": int(config.get("MRCN_SIGNATURE_HERO_BATCH_SIZE", "32")),
        "max_concurrency": int(config.get("MRCN_SIGNATURE_MAX_CONCURRENCY", "4")),
        "season_policy": str(config.get("MRCN_SIGNATURE_SEASON_POLICY", "independent")),
        "result_cache_seconds": float(config.get("MRCN_SIGNATURE_RESULT_CACHE_SECONDS", "900")),
        "historical_cache_seconds": float(config.get("MRCN_SIGNATURE_HISTORY_CACHE_SECONDS", "604800")),
        "current_cache_seconds": float(config.get("MRCN_SIGNATURE_CURRENT_CACHE_SECONDS", "1800")),
    }
    shadow_service = PlayerCareerAnalysisService(rivals, meta_service, rating_version="shadow", **common)
    v2_service = PlayerCareerAnalysisService(rivals, meta_service, rating_version="v2", **common)
    uid_limit = max(1, int(args.uid_concurrency))
    semaphore = asyncio.Semaphore(uid_limit)

    async def one(uid: str) -> dict[str, Any]:
        async with semaphore:
            print(f"[{uid}] 开始 Shadow/V2", flush=True)
            errors: list[dict[str, str]] = []
            shadow_profile: PlayerSignatureProfile | None = None
            v2_profile: PlayerSignatureProfile | None = None
            for version, service in (("shadow", shadow_service), ("v2", v2_service)):
                try:
                    profile = await service.get_analysis(uid)
                except Exception as exc:  # keep the batch moving for inaccessible UIDs
                    errors.append({"version": version, "type": type(exc).__name__, "message": str(exc)})
                    continue
                if version == "shadow":
                    shadow_profile = profile
                else:
                    v2_profile = profile
            shadow = _profile_record(shadow_profile)
            v2 = _profile_record(v2_profile)
            comparison = _comparison(shadow, v2) if shadow or v2 else None
            player_name = (shadow or v2 or {}).get("player_name", "未知")
            if shadow and v2 and not errors:
                status = "ok"
            elif shadow or v2:
                status = "partial"
            else:
                status = "failed"
            print(f"[{uid}] 完成 status={status} shadow={bool(shadow)} v2={bool(v2)}", flush=True)
            return {
                "uid": uid,
                "player_name": player_name,
                "status": status,
                "errors": errors,
                "shadow": shadow,
                "v2": v2,
                "comparison": comparison,
            }

    try:
        players = await asyncio.gather(*(one(uid) for uid in uids))
    finally:
        await source.aclose()
        if meta_source is not None:
            await meta_source.aclose()

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "career",
        "raw_uid_count": len(args.uids or (Path(args.uid_file).read_text(encoding="utf-8").split() if args.uid_file else DEFAULT_UIDS)),
        "input_uid_count": len(uids),
        "success_count": sum(item["status"] == "ok" for item in players),
        "partial_count": sum(item["status"] == "partial" for item in players),
        "failure_count": sum(item["status"] == "failed" for item in players),
        "players": players,
    }


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量生成 Player Rating Shadow/V2 对照报告")
    parser.add_argument("--env-file", default=".env.capture", help="KEY=value 配置文件")
    parser.add_argument("--uids", nargs="*", help="数字 UID；不传时使用脚本内置测试列表")
    parser.add_argument("--uid-file", help="按空格、逗号或换行分隔的 UID 文件")
    parser.add_argument("--cache-root", default="data/plugin_data/astrbot_plugin_marvel_rivals", help="插件数据根目录，用于复用正式缓存")
    parser.add_argument("--uid-concurrency", type=int, default=2, help="并行 UID 数，默认 2")
    parser.add_argument("--report", default="rating_shadow_v2_validation_report.md", help="Markdown 报告路径")
    parser.add_argument("--json-report", default="rating_shadow_v2_validation_report.json", help="JSON 报告路径")
    return parser


def main() -> None:
    args = make_parser().parse_args()
    if args.uids and args.uid_file:
        raise SystemExit("--uids 与 --uid-file 只能指定一个")
    report = asyncio.run(_build_report(args))
    report_path = Path(args.report).resolve()
    json_path = Path(args.json_report).resolve()
    report_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已生成：{report_path}")
    print(f"机器可读报告已生成：{json_path}")
    print(f"UID={report['input_uid_count']} 成功={report['success_count']} 部分成功={report['partial_count']} 失败={report['failure_count']}")


if __name__ == "__main__":
    main()
