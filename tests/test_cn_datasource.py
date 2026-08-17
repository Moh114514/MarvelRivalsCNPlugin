import json
import unittest

import httpx

from marvel_rivals_bot.datasource.cn import CNDataSource, _rank_text
from marvel_rivals_bot.models import PlayerStats


class TestCNDataSource(unittest.IsolatedAsyncioTestCase):
    async def test_body_template_and_response_normalization(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/role/loadByRoleId":
                calls.append((request.url.path, dict(request.url.params)))
                return httpx.Response(200, json={"data": {"roleId": "195963667", "roleName": "Noir"}})
            body = json.loads(request.content)
            calls.append((request.url.path, body))
            if request.url.path == "/api/game/player/loadCareer":
                values = (8, 5) if body["gameModeId"] == 1 else (12, 7)
                return httpx.Response(200, json={"data": {
                    "totalMatchCount": values[0], "totalMatchWinCount": values[1],
                }})
            if request.url.path == "/api/game/player/loadSortHero":
                matches, wins = (8, 5) if body["gameModeId"] == 1 else (12, 7)
                return httpx.Response(200, json={"data": {
                    "heroes": [{"heroId": "1", "heroName": "月光骑士", "matchCount": matches, "winCount": wins}],
                }})
            responses = {
                "/api/game/player/loadData": {"data": {"name": "Noir", "level": 33, "rankGameSeason": "钻石 I"}},
                "/api/game/player/loadSummary": {"data": {"totalMatchCount": 20, "totalMatchWinCount": 12, "k": 100, "d": 50, "a": 80}},
                "/api/game/player/loadCareer": {"data": {}},
                "/api/game/player/loadSortHero": {"data": {"heroes": [{"heroId": "1", "heroName": "月光骑士", "matchCount": 8, "winCount": 5}] }},
                "/api/game/player/loadHeroCareer": {"data": {"careers": [{"heroId": 1, "totalMatchCount": 8, "totalMatchWinCount": 5, "k": 42}]}},
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
        self.assertEqual(stats.heroes[0].matches, 20)
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
            if request.url.path.endswith("/loadSummaryDetail"):
                self.assertEqual(json.loads(request.content), {"matchUids": ["m-1"]})
                return httpx.Response(200, json={"data": {"matches": [{
                    "matchUid": "m-1",
                    "matchPlayers": [{"playerUid": 1, "curHeroId": 1036}],
                }]}})
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            matches = await source.get_recent_matches("1")
        self.assertEqual(matches[0]["matchUid"], "m-1")
        self.assertEqual(matches[0]["matchPlayer"]["curHeroId"], 1036)

    async def test_match_detail_accepts_copied_match_uid_prefix(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(json.loads(request.content))
            return httpx.Response(200, json={"data": {"matches": [{"matchUid": "m-1"}]}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            payload = await source.get_summary_detail("matchUid=m-1")

        self.assertEqual(calls, [{"matchUids": ["m-1"]}])
        self.assertEqual(payload["data"]["matches"][0]["matchUid"], "m-1")

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

    async def test_private_profile_error_without_de_particle_includes_hint(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "code": 403,
                "msg": "不允许查看该用户游戏数据",
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            with self.assertRaisesRegex(Exception, "漫威争锋小程序→战绩→设置"):
                await source.get_player("1")

    async def test_cn_response_field_names_are_normalized(self):
        responses = {
            "/api/game/player/loadData": {"data": {"name": "Moh233", "aid": 195963667, "level": 83}},
            "/api/game/player/loadSummary": {"data": {"matchInfo": []}},
            "/api/game/player/loadCareer": {"data": {"totalWinCount": 14, "totalMatchCount": 27, "k": 386, "d": 117, "a": 284}},
            "/api/game/player/loadSortHero": {"data": {"heros": [{"heroId": 1066, "totalPlayTime": 4338.3}]}},
            "/api/game/player/loadHeroCareer": {"data": {"careers": [{"heroId": 1066, "totalMatchCount": 10, "totalMatchWinCount": 7, "k": 186}]}},
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/loadByRoleId"):
                return httpx.Response(200, json={"data": {"roleId": 195963667}})
            if request.url.path.endswith("/loadCareer"):
                body = json.loads(request.content)
                if body["gameModeId"] == 1:
                    data = {"totalWinCount": 6, "totalMatchCount": 12, "k": 100, "d": 40, "a": 80}
                else:
                    data = {"totalWinCount": 8, "totalMatchCount": 15, "k": 286, "d": 77, "a": 204}
                return httpx.Response(200, json={"data": data})
            if request.url.path.endswith("/loadSortHero"):
                body = json.loads(request.content)
                data = {"heros": [{"heroId": 1066, "totalPlayTime": 4338.3, "k": 186}]} if body["gameModeId"] == 1 else {"heros": [{"heroId": 1066}]}
                return httpx.Response(200, json={"data": data})
            return httpx.Response(200, json=responses[request.url.path])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            stats = await source.get_player("195963667")
        self.assertEqual(stats.summary.wins, 14)
        self.assertEqual(stats.summary.matches, 27)
        self.assertEqual(stats.heroes[0].hero_id, "1066")
        self.assertEqual(stats.heroes[0].hero_name, "红兜帽")
        self.assertEqual(stats.heroes[0].play_time_seconds, 4338.3)
        self.assertIsNone(stats.heroes[0].matches)
        self.assertEqual(stats.heroes[0].kills, 186)

    async def test_career_array_and_mode_heroes_are_normalized(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/loadByRoleId"):
                return httpx.Response(200, json={"data": {"roleId": 1287101468}})
            body = json.loads(request.content)
            if request.url.path.endswith("/loadData"):
                data = {"aid": 1287101468}
            elif request.url.path.endswith("/loadCareer"):
                if body["gameModeId"] == 1:
                    data = {"career": None, "careers": [{
                        "playerUid": 1287101468, "totalMatchCount": 12,
                        "totalMatchWinCount": 6, "k": 180, "d": 50, "a": 100,
                    }]}
                else:
                    data = {"career": None, "careers": [{
                        "playerUid": 1287101468, "totalMatchCount": 15,
                        "totalMatchWinCount": 8, "k": 206, "d": 67, "a": 184,
                    }]}
            elif request.url.path.endswith("/loadSortHero"):
                data = {"heros": [
                    {"heroId": hero_id, "matchCount": 1, "winCount": 1}
                    for hero_id in range(1001, 1013)
                ]}
            else:
                data = {}
            return httpx.Response(200, json={"data": data})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            stats = await source.get_player("1287101468")

        self.assertEqual((stats.summary.matches, stats.summary.wins), (27, 14))
        self.assertEqual((stats.summary.kills, stats.summary.deaths, stats.summary.assists), (386, 117, 284))
        self.assertAlmostEqual(stats.summary.win_rate, 14 * 100 / 27)
        self.assertEqual(len(stats.heroes), 12)
        self.assertTrue(all(hero.matches == 2 for hero in stats.heroes))
        self.assertTrue(all(hero.quick.matches == 1 for hero in stats.heroes))
        self.assertTrue(all(hero.ranked.matches == 1 for hero in stats.heroes))

    async def test_quick_and_competitive_scopes_use_scalar_request_filters(self):
        career_filters = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/loadByRoleId"):
                return httpx.Response(200, json={"data": {"roleId": 1287101468}})
            body = json.loads(request.content)
            path = request.url.path
            if path.endswith("/loadData"):
                data = {"aid": 1287101468, "name": "Tester"}
            elif path.endswith("/loadCareer"):
                mode = body["gameModeId"]
                career_filters.append(mode)
                values = {1: (12, 6), 2: (8, 5)}[mode]
                data = {"totalMatchCount": values[0], "totalMatchWinCount": values[1]}
            elif path.endswith("/loadSortHero"):
                mode = body["gameModeId"]
                values = {1: (12, 6), 2: (8, 5)}[mode]
                data = {"heros": [{"heroId": 1066, "matchCount": values[0], "winCount": values[1]}]}
            else:
                data = {}
            return httpx.Response(200, json={"data": data})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            stats = await source.get_player("1287101468")

        self.assertEqual(career_filters, [1, 2])
        self.assertEqual((stats.summary.matches, stats.summary.quick.matches, stats.summary.ranked.matches), (20, 12, 8))
        hero = stats.heroes[0]
        self.assertEqual((hero.total_matches, hero.quick.matches, hero.ranked.matches), (20, 12, 8))
        self.assertEqual(hero.ranked.wins, 5)

    async def test_historical_season_is_sent_and_rank_is_mapped(self):
        calls = []
        rank_seasons = {"1001018": json.dumps({"level": 14, "rank_score": 4411.2})}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json={"data": {"roleId": 1287101468}})
            body = json.loads(request.content)
            calls.append((request.url.path, body))
            if request.url.path.endswith("/loadData"):
                data = {"aid": 1287101468, "rankGameSeason": json.dumps(rank_seasons)}
            elif request.url.path.endswith("/loadSortHero"):
                data = {"heros": [{"heroId": 1066, "k": 123}]} if body["gameModeId"] == 1 else {"heros": [{"heroId": 1066}]}
            else:
                data = {}
            return httpx.Response(200, json={"data": data})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            stats = await source.get_player("1287101468", "18")

        self.assertEqual(stats.season, "18")
        self.assertEqual(stats.profile.rank_level, 14)
        self.assertEqual(stats.profile.rank_game_season, "钻石2（4411 分）")
        self.assertEqual(stats.heroes[0].kills, 123)
        for path, body in calls:
            if not path.endswith("/loadData"):
                match_season = body["matchSeason"]
                self.assertEqual(match_season.get("$eq") if isinstance(match_season, dict) else match_season, "18")

    def test_rank_level_mapping(self):
        payload = json.dumps({
            "1001001": json.dumps({"level": 7}),
            "1001009": json.dumps({"level": 10}),
            "1001010": json.dumps({"level": 19}),
            "1001019": json.dumps({"level": 1}),
            "1001018": json.dumps({"level": 14}),
        })
        self.assertEqual(_rank_text(payload, "1"), "黄金3")
        self.assertEqual(_rank_text(payload, "9"), "铂金3")
        self.assertEqual(_rank_text(payload, "10"), "天神3")
        self.assertEqual(_rank_text(payload, "19"), "青铜3")
        self.assertEqual(_rank_text(payload, "18"), "钻石2")

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
        self.assertIn("{match_uids}", source.body_templates["summary_detail"])


if __name__ == "__main__":
    unittest.main()
