from __future__ import annotations

import argparse
import asyncio

from .datasource.cn import CNDataSource
from .services.rivals import format_player


async def _run(uid: str) -> None:
    print(format_player(await CNDataSource().get_player(uid)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Query Marvel Rivals CN stats")
    parser.add_argument("uid", help="numeric player UID")
    args = parser.parse_args()
    asyncio.run(_run(args.uid))

