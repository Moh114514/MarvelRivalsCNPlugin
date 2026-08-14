import json
import shutil
import unittest
from contextlib import contextmanager
from pathlib import Path

import httpx

from rendering.assets import AssetManager


PNG = b"\x89PNG\r\n\x1a\npng-payload"


class TestAssetManager(unittest.IsolatedAsyncioTestCase):
    @contextmanager
    def asset_directory(self, name: str):
        root = Path.cwd() / "tmp-assets" / name
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        try:
            yield str(root)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    async def test_lazy_cache_manifest_and_data_uri(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, headers={"content-type": "image/webp"}, content=b"RIFFxxxxWEBPpayload")

        with self.asset_directory("lazy") as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                manager = AssetManager(directory, client=client)
                path = await manager.get_hero_image("1036", "https://cdn.example/1036.webp")
                cached = await manager.get_hero_image("1036", "https://cdn.example/1036.webp")
                data_uri = manager.to_data_uri(path)

            self.assertIsNotNone(path)
            self.assertEqual(path, cached)
            self.assertTrue(Path(path).is_file())
            self.assertEqual(len(calls), 1)
            self.assertTrue(data_uri.startswith("data:image/webp;base64,"))
            manifest = json.loads((Path(directory) / "manifest.json").read_text(encoding="utf-8"))
            record = manifest["heroes"]["1036"]
            self.assertEqual(record["hero_id"], "1036")
            self.assertEqual(record["file"], "heroes/1036.webp")
            self.assertEqual(record["source_url"], "https://cdn.example/1036.webp")
            self.assertTrue(record["sha256"])
            self.assertFalse(list((Path(directory) / "heroes").glob("*.tmp")))

    async def test_url_change_and_conditional_revalidation(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.url.path.endswith("v1.webp") and len(calls) == 1:
                return httpx.Response(
                    200,
                    headers={"content-type": "image/webp", "etag": '"v1"', "last-modified": "yesterday"},
                    content=b"RIFFxxxxWEBPv1",
                )
            if request.url.path.endswith("v1.webp"):
                self.assertEqual(request.headers["If-None-Match"], '"v1"')
                self.assertEqual(request.headers["If-Modified-Since"], "yesterday")
                return httpx.Response(304, headers={"etag": '"v1"'})
            return httpx.Response(200, headers={"content-type": "image/webp"}, content=b"RIFFxxxxWEBPv2")

        with self.asset_directory("conditional") as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                manager = AssetManager(directory, client=client, refresh_days=0)
                first = await manager.get_hero_image("1036", "https://cdn.example/v1.webp")
                unchanged = await manager.get_hero_image("1036", "https://cdn.example/v1.webp")
                updated = await manager.get_hero_image("1036", "https://cdn.example/v2.webp")

            self.assertEqual(first, unchanged)
            self.assertEqual(Path(first).read_bytes(), b"RIFFxxxxWEBPv2")
            self.assertEqual(updated, first)
            self.assertEqual(len(calls), 3)

    async def test_warmup_is_partial_and_invalid_responses_fall_back(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("bad"):
                return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>error</html>")
            return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)

        with self.asset_directory("warmup") as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                manager = AssetManager(directory, client=client, max_concurrency=2)
                results = await manager.warmup({
                    "bad": "https://cdn.example/bad",
                    "good": "https://cdn.example/good.png",
                })

            self.assertIsNone(results["bad"])
            self.assertIsNotNone(results["good"])
            self.assertIsNone(await manager.get_hero_image("bad"))
            self.assertEqual(manager.status()["cached"], 1)

    async def test_stale_image_remains_available_when_refresh_fails(self):
        responses = [
            httpx.Response(200, headers={"content-type": "image/png"}, content=PNG),
            httpx.Response(503),
        ]

        def handler(_request: httpx.Request) -> httpx.Response:
            return responses.pop(0)

        with self.asset_directory("fallback") as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                manager = AssetManager(directory, client=client, refresh_days=0)
                first = await manager.get_hero_image("1011", "https://cdn.example/1011.png")
                fallback = await manager.get_hero_image("1011", "https://cdn.example/1011.png")

            self.assertEqual(first, fallback)
            self.assertTrue(Path(fallback).is_file())


if __name__ == "__main__":
    unittest.main()
