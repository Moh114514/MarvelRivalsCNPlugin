import asyncio
import math
import unittest

import httpx

from marvel_rivals_bot.meta.errors import MetaDataSourceError, MetaHTTPError, MetaSchemaError
from marvel_rivals_bot.meta.sources.rivalsmeta import RivalsMetaSource


def payload():
    return {
        "season": 18,
        "timestamp": 1720000000,
        "heroes": [
            {
                "rank": "6",
                "heroes": [
                    {"hero_id": "1020", "matches": 1020.0, "wins": "10", "wr_matches": 10, "wr_wins": 5, "mirror_matches": 0}
                ],
            }
        ],
        "bans": [{"rank": 6, "bans": [{"hero_id": 1020, "bans": 2}]}],
        "maps": [{"map_id": 1}],
        "teamups": [{"id": 1}],
    }


class TestRivalsMetaSource(unittest.IsolatedAsyncioTestCase):
    async def test_mock_transport_url_and_parse(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=payload())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await RivalsMetaSource(client=client).get_hero_stats("18")
        self.assertEqual(str(seen[0].url), "https://rivalsmeta.com/api/heroes/stats?season=18")
        self.assertEqual(result.season, 18)
        self.assertEqual(result.heroes[0].heroes[0].matches, 1020)
        self.assertEqual(result.raw["maps"], payload()["maps"])
        self.assertIsNotNone(result.fetched_at)

    async def test_retry_once_for_503(self):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(503) if calls == 1 else httpx.Response(200, json=payload())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await RivalsMetaSource(client=client).get_hero_stats("18")
        self.assertEqual(calls, 2)

    async def test_timeout_retries_once_without_real_network(self):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout("timeout", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(MetaDataSourceError):
                await RivalsMetaSource(client=client).get_hero_stats("18")
        self.assertEqual(calls, 2)

    async def test_schema_errors_and_no_retry_for_404(self):
        with self.assertRaises(MetaSchemaError):
            RivalsMetaSource().parse_payload([])
        with self.assertRaises(MetaSchemaError):
            RivalsMetaSource().parse_payload({"season": 18})
        with self.assertRaises(MetaSchemaError):
            bad = payload()
            bad["heroes"][0]["heroes"][0]["matches"] = 1020.5
            RivalsMetaSource().parse_payload(bad)
        with self.assertRaises(MetaSchemaError):
            bad = payload()
            bad["timestamp"] = {"unexpected": True}
            RivalsMetaSource().parse_payload(bad)
        for timestamp in (True, math.nan):
            with self.assertRaises(MetaSchemaError):
                bad = payload()
                bad["timestamp"] = timestamp
                RivalsMetaSource().parse_payload(bad)
        with self.assertRaises(MetaSchemaError):
            bad = payload()
            bad["heroes"][0]["rank"] = 99
            RivalsMetaSource().parse_payload(bad)

        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(MetaHTTPError):
                await RivalsMetaSource(client=client).get_hero_stats("18")
        self.assertEqual(calls, 1)

    async def test_response_season_must_match_requested_season(self):
        def handler(_request):
            bad = payload()
            bad["season"] = 19
            return httpx.Response(200, json=bad)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(MetaSchemaError):
                await RivalsMetaSource(client=client).get_hero_stats("18")

    async def test_request_season_must_be_numeric_api_code(self):
        with self.assertRaises(MetaDataSourceError):
            await RivalsMetaSource().get_hero_stats("S9")


if __name__ == "__main__":
    unittest.main()
