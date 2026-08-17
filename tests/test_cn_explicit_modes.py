import json
import unittest

import httpx

from marvel_rivals_bot.datasource.cn import CNDataSource, GameMode


class TestCNExplicitModes(unittest.IsolatedAsyncioTestCase):
    def test_mode_enum_values(self):
        self.assertEqual(GameMode.QUICK, 1)
        self.assertEqual(GameMode.COMPETITIVE, 2)

    async def test_explicit_endpoints_send_scalar_mode_fields(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            calls.append((request.url.path, body))
            return httpx.Response(200, json={"data": {}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            await source.load_career("123", "18", GameMode.COMPETITIVE)
            await source.load_sort_hero("123", "18", GameMode.QUICK)
            await source.load_hero_career("123", [1031], "18", GameMode.COMPETITIVE)

        self.assertEqual(calls[0][1], {
            "matchSeason": "18",
            "gameModeId": 2,
            "playModeId": 0,
            "playerUid": 123,
        })
        self.assertEqual(calls[1][1]["gameModeId"], 1)
        self.assertEqual(calls[1][1]["playModeId"], 0)
        self.assertEqual(calls[2][1], {
            "heroIdList": [1031],
            "matchSeason": "18",
            "gameModeId": 2,
            "playModeId": 0,
            "playerUid": 123,
        })

    async def test_player_uses_two_career_and_two_sorted_hero_requests(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/loadByRoleId"):
                return httpx.Response(200, json={"data": {"roleId": 123}})
            body = json.loads(request.content)
            calls.append((path, body))
            if path.endswith("/loadData"):
                data = {"aid": 123, "name": "Tester", "level": 83}
            elif path.endswith("/loadCareer"):
                quick = body["gameModeId"] == 1
                data = {
                    "totalMatchCount": 12 if quick else 8,
                    "totalMatchWinCount": 6 if quick else 5,
                }
            elif path.endswith("/loadSortHero"):
                quick = body["gameModeId"] == 1
                data = {
                    "heros": [
                        {"heroId": 1031, "matchCount": 40 if quick else 10},
                        {"heroId": 1032, "matchCount": 20 if quick else 25},
                    ]
                }
            else:
                self.fail(f"unexpected endpoint: {path}")
            return httpx.Response(200, json={"data": data})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            stats = await source.get_player("123", "18")

        self.assertEqual(stats.summary.matches, 20)
        self.assertEqual(stats.summary.quick.matches, 12)
        self.assertEqual(stats.summary.competitive.matches, 8)
        self.assertEqual(
            [(hero.hero_id, hero.total_matches) for hero in stats.heroes],
            [("1031", 50), ("1032", 45)],
        )
        self.assertEqual([path for path, _body in calls].count("/api/game/player/loadCareer"), 2)
        self.assertEqual([path for path, _body in calls].count("/api/game/player/loadSortHero"), 2)

    async def test_configured_competitive_template_overrides_generic_template(self):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.assertEqual(body["marker"], "competitive")
            return httpx.Response(200, json={"data": {}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={
                "MRCN_API_BASE_URL": "https://example.test",
                "MRCN_CAREER_COMPETITIVE_BODY_TEMPLATE": (
                    '{"matchSeason":"{season}","gameModeId":2,"playModeId":0,'
                    '"playerUid":{player_uid},"marker":"competitive"}'
                ),
            })
            await source.load_career("123", "18", GameMode.COMPETITIVE)

    async def test_profile_only_loader_does_not_request_statistics(self):
        paths = []

        def handler(request: httpx.Request) -> httpx.Response:
            paths.append(request.url.path)
            if request.method == "GET":
                return httpx.Response(200, json={"data": {"roleId": 123}})
            return httpx.Response(200, json={"data": {"aid": 123, "level": 83}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            profile = await source.get_player_profile("123", "18")

        self.assertEqual(profile.uid, "123")
        self.assertEqual(paths, ["/api/role/loadByRoleId", "/api/game/player/loadData"])


if __name__ == "__main__":
    unittest.main()
