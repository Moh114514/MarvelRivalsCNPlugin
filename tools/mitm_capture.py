"""mitmproxy addon for discovering Marvel Rivals CN mini-program APIs.

Run with:
    mitmdump -s tools/mitm_capture.py --set capture_dir=captures

The addon writes request/response samples and a plugin-ready JSON config. It
redacts Cookie/Authorization/token-like headers by default. Set
MRCN_CAPTURE_INCLUDE_SENSITIVE=1 only when the local capture directory is
protected and the temporary credentials are needed for a live PoC.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mitmproxy import ctx, http


BASE_HOST = "s3.game.163.com"
KNOWN_ENDPOINTS = {
    "data": "/api/game/player/loadData",
    "summary": "/api/game/player/loadSummary",
    "career": "/api/game/player/loadCareer",
    "hero": "/api/game/player/loadHeroCareer",
    "sort_hero": "/api/game/player/loadSortHero",
}
SENSITIVE_HEADERS = re.compile(r"^(authorization|proxy-authorization|cookie|set-cookie|x-api-key|x-token|token|sign|signature)$", re.I)
UID_PATTERN = re.compile(r"(?<!\d)\d{5,}(?!\d)")


def _json_body(flow: http.HTTPFlow) -> Any:
    if not flow.request.raw_content:
        return None
    try:
        return json.loads(flow.request.get_text(strict=False))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _redact_headers(headers: http.Headers) -> dict[str, str]:
    include_sensitive = os.getenv("MRCN_CAPTURE_INCLUDE_SENSITIVE") == "1"
    result = {}
    for key, value in headers.items(multi=True):
        result[key] = value if include_sensitive or not SENSITIVE_HEADERS.match(key) else "<redacted>"
    return result


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return UID_PATTERN.sub("{uid}", value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    return value


def _classify(path: str) -> str | None:
    normalized = path.split("?", 1)[0]
    for name, known_path in KNOWN_ENDPOINTS.items():
        if normalized.endswith(known_path):
            return name
    lower = normalized.lower()
    if any(word in lower for word in ("match", "battle", "history", "record", "recent")):
        return "matches"
    return None


class MarvelRivalsCapture:
    def __init__(self) -> None:
        self.samples: list[dict[str, Any]] = []
        self.config: dict[str, dict[str, Any]] = {}

    def load(self, loader) -> None:
        loader.add_option("capture_dir", str, "captures", "Directory for Marvel Rivals capture output")

    def request(self, flow: http.HTTPFlow) -> None:
        if flow.request.host != BASE_HOST:
            return
        category = _classify(flow.request.path)
        if category is None:
            return
        body = _json_body(flow)
        sample = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "request": {
                "method": flow.request.method,
                "url": flow.request.pretty_url,
                "path": flow.request.path.split("?", 1)[0],
                "headers": _redact_headers(flow.request.headers),
                "body": _redact_value(body),
            },
        }
        flow.metadata["mrcn_capture"] = sample

    def response(self, flow: http.HTTPFlow) -> None:
        sample = flow.metadata.get("mrcn_capture")
        if not sample:
            return
        response_body = None
        if flow.response:
            try:
                response_body = json.loads(flow.response.get_text(strict=False))
            except (UnicodeDecodeError, json.JSONDecodeError):
                response_body = {"content_type": flow.response.headers.get("content-type", "")}
            sample["response"] = {
                "status_code": flow.response.status_code,
                "headers": _redact_headers(flow.response.headers),
                "body": _redact_value(response_body),
            }
        self.samples.append(sample)
        self.config[sample["category"]] = {
            "path": sample["request"]["path"],
            "body": sample["request"]["body"],
            "headers": sample["request"]["headers"],
        }
        self._write()

    def _write(self) -> None:
        directory = Path(ctx.options.capture_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "flows.json").write_text(json.dumps(self.samples, ensure_ascii=False, indent=2), encoding="utf-8")
        config = self._plugin_config()
        (directory / "mrcn_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    def _plugin_config(self) -> dict[str, Any]:
        latest = next(iter(reversed(self.config.values())), {})
        base_url = ""
        for sample in self.samples:
            url = sample["request"]["url"]
            if "://" in url:
                scheme, rest = url.split("://", 1)
                host = rest.split("/", 1)[0]
                base_url = f"{scheme}://{host}"
                prefix = sample["request"]["path"].split("/api/", 1)[0]
                if prefix:
                    base_url += prefix
                break
        result = {"MRCN_API_BASE_URL": base_url, "MRCN_HEADERS_JSON": json.dumps(latest.get("headers", {}), ensure_ascii=False)}
        body = latest.get("body")
        if isinstance(body, dict):
            result["MRCN_REQUEST_BODY_TEMPLATE"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        for category, item in self.config.items():
            result[f"MRCN_{category.upper()}_PATH"] = item["path"]
        if os.getenv("MRCN_CAPTURE_INCLUDE_SENSITIVE") != "1":
            result["MRCN_CAPTURE_WARNING"] = "Sensitive headers were redacted. Re-capture with MRCN_CAPTURE_INCLUDE_SENSITIVE=1 for a live authenticated PoC."
        return result


addons = [MarvelRivalsCapture()]

