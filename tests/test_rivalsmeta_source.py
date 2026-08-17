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
        self.assertEqual(result.bans[0].rank_code, "6")
        self.assertEqual(result.bans[0].bans[0].hero_id, 1020)
        self.assertEqual(result.bans[0].bans[0].bans, 2)
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

    async def test_read_error_and_connection_reset_retry_once(self):
        for failure in (
            lambda request: httpx.ReadError("read", request=request),
            lambda request: ConnectionResetError("reset"),
        ):
            calls = 0

            def handler(request):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise failure(request)
                return httpx.Response(200, json=payload())

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await RivalsMetaSource(client=client).get_hero_stats("18")
            self.assertEqual(calls, 2)

    async def test_other_network_errors_do_not_retry(self):
        for error_type in (httpx.ConnectError, httpx.WriteError):
            calls = 0

            def handler(request):
                nonlocal calls
                calls += 1
                raise error_type("network", request=request)

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(MetaDataSourceError):
                    await RivalsMetaSource(client=client).get_hero_stats("18")
            self.assertEqual(calls, 1)

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
            bad["timestamp"] = -1
            RivalsMetaSource().parse_payload(bad)
        with self.assertRaises(MetaSchemaError):
            bad = payload()
            bad["heroes"][0]["rank"] = 99
            RivalsMetaSource().parse_payload(bad)
        with self.assertRaises(MetaSchemaError):
            bad = payload()
            bad["heroes"].append(bad["heroes"][0].copy())
            RivalsMetaSource().parse_payload(bad)
        with self.assertRaises(MetaSchemaError):
            bad = payload()
            bad["bans"].append(bad["bans"][0].copy())
            RivalsMetaSource().parse_payload(bad)
        for field, value in (
            ("season", -1),
            ("hero_id", -1020),
            ("matches", -1),
            ("bans", -1),
        ):
            with self.assertRaises(MetaSchemaError):
                bad = payload()
                if field == "season":
                    bad[field] = value
                elif field == "bans":
                    bad["bans"][0]["bans"][0][field] = value
                else:
                    bad["heroes"][0]["heroes"][0][field] = value
                RivalsMetaSource().parse_payload(bad)

        for status in (400, 404, 500):
            calls = 0

            def handler(_request):
                nonlocal calls
                calls += 1
                return httpx.Response(status)

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
