import json
import unittest

import httpx

from marvel_rivals_bot.datasource.cn import CNDataSource
from marvel_rivals_bot.models import PlayerStats


class TestCNDataSource(unittest.IsolatedAsyncioTestCase):
    async def test_body_template_and_response_normalization(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/role/loadByRoleId":
                calls.append((request.url.path, dict(request.url.params)))
                return httpx.Response(200, json={"data": {"roleId": "195963667", "roleName": "Noir"}})
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
        self.assertEqual(calls[0][1], {"roleId": "195963667"})
        self.assertEqual(calls[1][1], {"aid": "195963667", "zoneId": 16001})

    async def test_recent_matches_uses_confirmed_summary_path(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/loadByRoleId"):
                return httpx.Response(200, json={"data": {"roleId": 1}})
            if request.url.path.endswith("/loadData"):
                return httpx.Response(200, json={"data": {"aid": 1}})
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

    async def test_private_profile_error_includes_permission_hint(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "code": 403,
                "msg": "不允许查看该用户的游戏数据",
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            with self.assertRaisesRegex(
                Exception,
                "不允许查看该用户的游戏数据[\\s\\S]*漫威争锋小程序→战绩→设置[\\s\\S]*打开查询权限",
            ):
                await source.get_player("1")

    async def test_cn_response_field_names_are_normalized(self):
        responses = {
            "/api/game/player/loadData": {"data": {"name": "Moh233", "aid": 195963667, "level": 83}},
            "/api/game/player/loadSummary": {"data": {"matchInfo": []}},
            "/api/game/player/loadCareer": {"data": {"totalWinCount": 14, "totalMatchCount": 27, "k": 386, "d": 117, "a": 284}},
            "/api/game/player/loadSortHero": {"data": {"heros": [{"heroId": 1066, "totalPlayTime": 4338.3}]}},
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/loadByRoleId"):
                return httpx.Response(200, json={"data": {"roleId": 195963667}})
            return httpx.Response(200, json=responses[request.url.path])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            stats = await source.get_player("195963667")
        self.assertEqual(stats.summary.wins, 14)
        self.assertEqual(stats.summary.matches, 27)
        self.assertEqual(stats.heroes[0].hero_id, "1066")
        self.assertEqual(stats.heroes[0].play_time_seconds, 4338.3)

    async def test_response_rejects_different_requested_uid(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            if request.url.path.endswith("/loadByRoleId"):
                return httpx.Response(200, json={"data": {"roleId": 578402658}})
            return httpx.Response(200, json={"data": {"name": "Moh233", "aid": 195963667}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            with self.assertRaisesRegex(Exception, "请求 578402658.*服务器返回 195963667"):
                await source.get_player("578402658")
        self.assertEqual(calls, ["/api/role/loadByRoleId", "/api/game/player/loadData"])

    async def test_profile_uses_uid_returned_by_server(self):
        responses = {
            "/api/game/player/loadData": {"data": {"name": "Moh233", "aid": 195963667}},
            "/api/game/player/loadSummary": {"data": {}},
            "/api/game/player/loadCareer": {"data": {"playerUid": 195963667}},
            "/api/game/player/loadSortHero": {"data": {"heros": []}},
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/loadByRoleId"):
                return httpx.Response(200, json={"data": {"roleId": 195963667}})
            return httpx.Response(200, json=responses[request.url.path])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            stats = await source.get_player("195963667")
        self.assertEqual(stats.profile.uid, "195963667")

    async def test_target_uid_is_sent_to_every_player_endpoint(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                calls.append((request.url.path, dict(request.url.params)))
                return httpx.Response(200, json={"data": {"roleId": 1287101468}})
            body = json.loads(request.content)
            calls.append((request.url.path, body))
            data = {"aid": 1287101468} if request.url.path.endswith("/loadData") else {}
            if request.url.path.endswith("/loadCareer"):
                data = {"playerUid": 1287101468}
            return httpx.Response(200, json={"data": data})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            await source.get_player("1287101468")

        self.assertEqual(calls[0][1], {"roleId": "1287101468"})
        for _path, body in calls[1:]:
            self.assertEqual(body["playerUid"], 1287101468)

    def test_legacy_templates_are_upgraded_with_player_uid(self):
        source = CNDataSource(env={
            "MRCN_API_BASE_URL": "https://example.test",
            "MRCN_DATA_BODY_TEMPLATE": "{}",
            "MRCN_CAREER_BODY_TEMPLATE": '{"matchSeason":"19"}',
            "MRCN_HERO_BODY_TEMPLATE": '{"heroIdList":{hero_ids},"matchSeason":"19"}',
            "MRCN_SORT_HERO_BODY_TEMPLATE": '{"matchSeason":"19"}',
            "MRCN_SUMMARY_BODY_TEMPLATE": '{"page":0,"pageSize":3}',
            "MRCN_MATCHES_BODY_TEMPLATE": '{"page":0,"pageSize":10}',
        })
        for name in ("data", "summary", "career", "hero", "sort_hero", "matches"):
            self.assertIn("{player_uid}", source.body_templates[name])


if __name__ == "__main__":
    unittest.main()
