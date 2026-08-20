import asyncio
import unittest

from marvel_rivals_bot.models import PlayerProfile, PlayerStats
from marvel_rivals_bot.services.rivals import RivalsService


class _Source:
    default_season = "19"

    def __init__(self):
        self.calls = {"player": 0, "recent": 0, "hero": 0, "match": 0}
        self.active = 0
        self.maximum = 0
        self.release = asyncio.Event()
        self.fail_recent_once = False

    async def _hold(self):
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        await self.release.wait()
        self.active -= 1

    async def get_player(self, uid, season):
        self.calls["player"] += 1
        await self._hold()
        return PlayerStats(profile=PlayerProfile(uid=uid), season=season)

    async def get_recent_matches(self, uid, season):
        self.calls["recent"] += 1
        if self.fail_recent_once:
            self.fail_recent_once = False
            raise RuntimeError("temporary")
        await self._hold()
        return [{"matchUid": f"{uid}-{season}"}]

    async def get_hero(self, uid, hero_id, season):
        self.calls["hero"] += 1
        await self._hold()
        return {"data": {"careers": [{"heroId": int(hero_id)}]}}

    async def get_summary_detail(self, match_uid):
        self.calls["match"] += 1
        await self._hold()
        return {"data": {"matches": [{"matchUid": match_uid}]}}


class TestRivalsServiceConcurrency(unittest.IsolatedAsyncioTestCase):
    async def test_same_key_singleflight_covers_all_query_methods(self):
        source = _Source()
        service = RivalsService(source, cache_seconds=0, max_inflight_requests=4)
        calls = (
            [service.get_player_stats("1", "S9") for _ in range(4)],
            [service.get_hero_stats("1", "蜘蛛侠", "S9") for _ in range(4)],
            [service.get_recent_matches("1", "S9") for _ in range(4)],
            [service.get_match_detail("match-1") for _ in range(4)],
        )

        tasks = [asyncio.create_task(coro) for group in calls for coro in group]
        async def wait_for_one_call_per_key():
            while sum(source.calls.values()) < 4:
                await asyncio.sleep(0)

        await asyncio.wait_for(wait_for_one_call_per_key(), timeout=1)
        self.assertEqual(source.calls, {"player": 1, "recent": 1, "hero": 1, "match": 1})
        source.release.set()
        await asyncio.gather(*tasks)
        self.assertEqual(service._inflight, {})

    async def test_failed_singleflight_is_cleaned_and_can_run_again(self):
        source = _Source()
        source.fail_recent_once = True
        service = RivalsService(source, cache_seconds=0)

        with self.assertRaisesRegex(RuntimeError, "temporary"):
            await service.get_recent_matches("1", "S9")
        self.assertEqual(service._inflight, {})

        result_task = asyncio.create_task(service.get_recent_matches("1", "S9"))
        await asyncio.sleep(0)
        source.release.set()
        self.assertEqual((await result_task)[0]["matchUid"], "1-18")
        self.assertEqual(source.calls["recent"], 2)

    async def test_global_request_semaphore_limits_distinct_external_calls(self):
        source = _Source()
        service = RivalsService(source, cache_seconds=0, max_inflight_requests=2)
        tasks = [
            asyncio.create_task(service.get_player_stats(str(index), "S9"))
            for index in range(4)
        ]

        async def wait_for_two_calls():
            while source.calls["player"] < 2:
                await asyncio.sleep(0)

        await asyncio.wait_for(wait_for_two_calls(), timeout=1)
        self.assertEqual(source.maximum, 2)
        self.assertEqual(source.calls["player"], 2)
        source.release.set()
        await asyncio.gather(*tasks)
        self.assertEqual(source.maximum, 2)


if __name__ == "__main__":
    unittest.main()
