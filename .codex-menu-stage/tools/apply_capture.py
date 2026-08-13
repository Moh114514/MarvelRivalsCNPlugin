"""Validate and apply a mitm capture config to a local env file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?", default="captures/mrcn_config.json")
    parser.add_argument("--output", default=".env.capture")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    required = {"MRCN_API_BASE_URL", "MRCN_REQUEST_BODY_TEMPLATE"}
    missing = sorted(required - config.keys())
    if missing:
        raise SystemExit(f"capture config missing: {', '.join(missing)}")
    lines = []
    for key, value in config.items():
        if key.startswith("MRCN_") and not key.endswith("WARNING"):
            lines.append(f"{key}={value}")
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

