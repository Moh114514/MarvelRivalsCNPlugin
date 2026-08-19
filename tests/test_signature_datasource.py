import json
import unittest

import httpx

from marvel_rivals_bot.datasource.base import GameMode
from marvel_rivals_bot.datasource.cn import CNDataSource
from marvel_rivals_bot.models import PlayerProfile
from marvel_rivals_bot.services.rivals import RivalsService


class TestSignatureDatasource(unittest.IsolatedAsyncioTestCase):
    async def test_cn_profile_history_keeps_single_season_fields_and_maps_all_seasons(self):
        rank_history = {
            "1001018": json.dumps({"level": 14}),
            "1001019": json.dumps({"level": 16}),
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json={"data": {"roleId": 123}})
            return httpx.Response(200, json={
                "data": {
                    "aid": 123,
                    "name": "Tester",
                    "rankGameSeason": json.dumps(rank_history),
                },
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            profile = await source.get_player_profile_history("123")
            historical_profile = await source.get_player_profile("123", "18")

        self.assertEqual(profile.rank_history, {"18": 14, "19": 16})
        self.assertEqual(profile.rank_game_season_levels, profile.rank_history)
        self.assertEqual((historical_profile.rank_level, historical_profile.rank_game_season), (14, "钻石2"))

    async def test_batch_hero_career_uses_one_multi_id_request_and_omits_missing_rows(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            calls.append(body)
            self.assertEqual(body["heroIdList"], [1031, 1032, 1033])
            return httpx.Response(200, json={"data": {"careers": [
                {"heroId": 1031, "totalMatchCount": 8, "totalMatchWinCount": 5},
                {"heroId": 1032, "totalMatchCount": 2, "totalMatchWinCount": 1},
            ]}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            service = RivalsService(source, cache_seconds=0)
            profiles = await service.get_hero_profiles_batch(
                "123", [1031, 1032, 1033], "S9", GameMode.COMPETITIVE
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(
            [(profile.hero_id, profile.competitive.matches, profile.competitive.wins) for profile in profiles],
            [("1031", 8, 5), ("1032", 2, 1)],
        )
        self.assertNotIn("1033", {profile.hero_id for profile in profiles})

    async def test_service_profile_history_prefers_source_capability_and_legacy_fallback(self):
        class PreferredSource:
            async def get_player_profile_history(self, uid):
                return PlayerProfile(uid=uid, rank_history={"18": 14})

        class LegacySource:
            async def get_player_profile(self, uid, season=None):
                return PlayerProfile(uid=uid, rank_history={"18": 13})

        preferred = RivalsService(PreferredSource())
        legacy = RivalsService(LegacySource())
        self.assertEqual((await preferred.get_player_profile_history("1")).rank_history, {"18": 14})
        self.assertEqual((await legacy.get_player_profile_history("1")).rank_history, {"18": 13})


if __name__ == "__main__":
    unittest.main()
