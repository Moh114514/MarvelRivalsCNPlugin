from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from .datasource.base import DataSourceError
from .datasource.cn import CNDataSource
from .services.rivals import format_hero, format_match_detail, format_matches, format_player


def load_env_file(path: str | Path) -> dict[str, str]:
    """Load simple KEY=value config without printing secrets."""
    values: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_config(env_file: str | None) -> dict[str, Any]:
    config: dict[str, Any] = dict(os.environ)
    if env_file:
        config.update(load_env_file(env_file))
    return config


def print_config(config: dict[str, Any]) -> None:
    headers = config.get("MRCN_HEADERS_JSON", "{}")
    try:
        header_names = sorted(json.loads(headers).keys()) if isinstance(headers, str) else sorted(headers.keys())
    except (TypeError, json.JSONDecodeError):
        header_names = ["<invalid JSON>"]
    print(f"base_url: {config.get('MRCN_API_BASE_URL', '<missing>')}")
    print(f"access_token: {'configured' if config.get('MRCN_ACCESS_TOKEN') else 'missing'}")
    print(f"header_names: {', '.join(header_names) or '<none>'}")
    print(f"matches_path: {config.get('MRCN_MATCHES_PATH', '/api/game/player/loadSummary')}")
    print(f"ca_cert: {config.get('MRCN_CA_CERT', '<system CA>')}")
    print(f"verify_ssl: {config.get('MRCN_VERIFY_SSL', 'true')}")
    print(f"proxy: {'configured' if config.get('MRCN_PROXY') else '<none from plugin config>'}")
    print(f"trust_env: {config.get('MRCN_TRUST_ENV', 'false')}")


def save_raw(payload: Any, output: str | None) -> None:
    if not output:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"原始响应已保存：{path.resolve()}")


async def run(args: argparse.Namespace) -> None:
    config = build_config(args.env_file)
    if args.command == "config-check":
        print_config(config)
        return
    if args.debug:
        config["MRCN_DEBUG"] = "1"
    source = CNDataSource(env=config)
    try:
        if args.command == "player":
            player = await source.get_player(args.uid)
            print(format_player(player))
            save_raw(player.raw, args.raw_output)
        elif args.command == "recent":
            payload = await source.get_recent_payload(args.uid)
            save_raw(payload, args.raw_output)
            value = payload.get("data", payload)
            if isinstance(value, dict):
                value = value.get("matchInfo", value.get("matches", value.get("matchList", value.get("records", value.get("list", [])))))
            matches = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
            print(format_matches(matches))
        elif args.command == "hero":
            payload = await source.get_hero(args.uid, args.hero_id)
            save_raw(payload, args.raw_output)
            print(format_hero(payload))
        elif args.command == "match":
            payload = await source.get_summary_detail(args.match_uid)
            save_raw(payload, args.raw_output)
            print(format_match_detail(payload))
    except DataSourceError as exc:
        raise SystemExit(f"查询失败：{exc}") from exc
    finally:
        await source.aclose()


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Marvel Rivals CN API command-line debugger")
    parser.add_argument("--env-file", default=".env.capture", help="KEY=value config file; default: .env.capture")
    parser.add_argument("--debug", action="store_true", help="print request bodies and response top-level keys")
    parser.add_argument("--raw-output", help="save the complete JSON response to this local file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("config-check", help="validate local API configuration without making a request")
    player = sub.add_parser("player", help="query player aggregate data")
    player.add_argument("uid", help="numeric UID label; current access_token determines the account")
    recent = sub.add_parser("recent", help="query recent match list")
    recent.add_argument("uid", help="numeric UID label")
    hero = sub.add_parser("hero", help="query one hero")
    hero.add_argument("hero_id", help="hero ID, for example 1066")
    hero.add_argument("uid", help="numeric UID label")
    match = sub.add_parser("match", help="query one match detail")
    match.add_argument("match_uid", help="matchUid returned by recent")
    return parser


def main() -> None:
    parser = make_parser()
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
