import json
import unittest

import httpx

from marvel_rivals_bot.datasource.cn import CNDataSource
from marvel_rivals_bot.models import PlayerStats


class TestCNDataSource(unittest.IsolatedAsyncioTestCase):
    async def test_body_template_and_response_normalization(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.url.path, json.loads(request.content)))
            responses = {
                "/api/game/player/loadData": {"data": {"name": "Noir", "level": 33, "rankGameSeason": "钻石 I"}},
                "/api/game/player/loadSummary": {"data": {"totalMatchCount": 20, "totalMatchWinCount": 12, "k": 100, "d": 50, "a": 80}},
                "/api/game/player/loadCareer": {"data": {}},
                "/api/game/player/loadSortHero": {"data": {"heroes": [{"heroId": "1", "heroName": "月光骑士", "matchCount": 8, "winCount": 5}] }},
            }
            return httpx.Response(200, json=responses[request.url.path])

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test", "MRCN_REQUEST_BODY_TEMPLATE": '{"aid":"{uid}","zoneId":16001}'})
            stats = await source.get_player("195963667")
        self.assertIsInstance(stats, PlayerStats)
        self.assertEqual(stats.profile.name, "Noir")
        self.assertEqual(stats.summary.win_rate, 60)
        self.assertEqual(stats.heroes[0].hero_name, "月光骑士")
        self.assertEqual(calls[0][1], {"aid": "195963667", "zoneId": 16001})

    async def test_recent_matches_uses_confirmed_summary_path(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/loadSummary"):
                return httpx.Response(200, json={"data": {"list": [{"matchUid": "m-1"}]}})
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            matches = await source.get_recent_matches("1")
        self.assertEqual(matches[0]["matchUid"], "m-1")

    async def test_recent_matches_rejects_non_numeric_uid(self):
        source = CNDataSource(env={"MRCN_API_BASE_URL": "https://example.test", "MRCN_MATCHES_PATH": "/matches"})
        with self.assertRaisesRegex(Exception, "UID 必须是数字"):
            await source.get_recent_matches('1"}')

    async def test_business_error_is_not_treated_as_empty_player(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"code": 401, "msg": "token expired"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            with self.assertRaisesRegex(Exception, "业务失败"):
                await source.get_player("1")


if __name__ == "__main__":
    unittest.main()
