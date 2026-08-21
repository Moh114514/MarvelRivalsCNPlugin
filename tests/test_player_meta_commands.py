import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from main import MarvelRivalsPlugin
from marvel_rivals_bot.analytics.models import AnalysisScope
from tests.test_player_meta_rendering import _profile


class FakeEvent:
    def get_sender_id(self):
        return "qq-1"

    def plain_result(self, text):
        return ("text", text)

    def image_result(self, url):
        return ("image", url)


def plugin_with(profile=None, *, bound_uid="123", render_error=None):
    sickness_profile = SimpleNamespace(
        uid="123",
        player_name="玩家",
        first_season="S7",
        latest_season="S9.5",
        competitive_matches=20,
        meta_coverage=100.0,
        partial=False,
        meta_source="RivalsMeta",
        meta_source_timestamp=None,
        meta_stale=False,
        sick_heroes=(),
    )
    plugin = MarvelRivalsPlugin.__new__(MarvelRivalsPlugin)
    plugin.player_meta_service = SimpleNamespace(
        get_player_environment=AsyncMock(return_value=profile or _profile()),
        get_player_hero_pool=AsyncMock(return_value=profile or _profile()),
        get_player_signature=AsyncMock(return_value=profile or _profile()),
    )
    plugin.player_signature_service = SimpleNamespace(
        get_player_signature=AsyncMock(
            side_effect=[profile or _profile(), sickness_profile, profile or _profile(), sickness_profile]
        ),
    )
    pool = SimpleNamespace(
        uid="123",
        player_name="玩家",
        scope=AnalysisScope.career(),
        total_matches=100,
        active_heroes=1,
        core_heroes=(),
        top1_share=100.0,
        top3_share=100.0,
        effective_pool_width=1.0,
        vanguard_share=0.0,
        duelist_share=100.0,
        strategist_share=0.0,
        weighted_performance=0.0,
        positive_usage_share=0.0,
        negative_usage_share=0.0,
        structure_tags=(),
        meta_available=True,
        meta_stale=False,
    )
    plugin.player_career_analysis_service = SimpleNamespace(
        get_hero_pool_analysis=AsyncMock(return_value=pool),
        get_player_signature=plugin.player_signature_service.get_player_signature,
    )
    plugin.player_signature_service = plugin.player_career_analysis_service
    plugin.bindings = SimpleNamespace(get=lambda _qq: bound_uid)
    plugin.qq_card_sender = SimpleNamespace(supports=lambda _event: False)
    plugin.image_renderer = SimpleNamespace(
        player_meta_environment=AsyncMock(side_effect=render_error, return_value="environment.png"),
        player_hero_pool=AsyncMock(side_effect=render_error, return_value="pool.png"),
        player_hero_pool_analysis=AsyncMock(side_effect=render_error, return_value="pool.png"),
        player_signature=AsyncMock(side_effect=render_error, return_value="signature.png"),
        player_sickness=AsyncMock(side_effect=render_error, return_value="sickness.png"),
    )
    return plugin


class TestPlayerMetaCommands(unittest.IsolatedAsyncioTestCase):
    async def test_commands_use_bound_uid_and_send_image(self):
        plugin = plugin_with()
        event = FakeEvent()
        environment = [item async for item in plugin.my_environment(event, "S9.5", "")]
        pool = [item async for item in plugin.my_hero_pool(event, "S9.5", "")]
        signature = [item async for item in plugin.my_signature(event, "", "")]
        sickness = [item async for item in plugin.my_sickness(event, "", "")]
        self.assertEqual(environment, [("image", "environment.png")])
        self.assertEqual(pool, [("image", "pool.png")])
        self.assertEqual(signature, [("image", "signature.png")])
        self.assertEqual(sickness, [("image", "sickness.png")])
        plugin.player_meta_service.get_player_environment.assert_awaited_once_with("123", season="S9.5")
        plugin.player_career_analysis_service.get_hero_pool_analysis.assert_awaited_once_with(
            "123", AnalysisScope.season("19")
        )
        self.assertEqual(plugin.player_signature_service.get_player_signature.await_count, 2)
        self.assertEqual(
            plugin.player_signature_service.get_player_signature.await_args_list,
            [(("123",), {"top_n": 5}), (("123",), {"top_n": 5})],
        )

    async def test_missing_binding_is_explicit(self):
        plugin = plugin_with(bound_uid=None)
        result = [item async for item in plugin.my_environment(FakeEvent())]
        self.assertEqual(result[0][0], "text")
        self.assertIn("绑定账号", result[0][1])

    async def test_meta_commands_accept_explicit_uid_without_binding(self):
        plugin = plugin_with(bound_uid=None)
        event = FakeEvent()

        environment = [item async for item in plugin.my_environment(event, "1287101468", "S9.5")]
        pool = [item async for item in plugin.my_hero_pool(event, "S9.5", "uid=1287101468")]
        signature = [item async for item in plugin.my_signature(event, "1287101468", "")]
        sickness = [item async for item in plugin.my_sickness(event, "1287101468", "")]

        self.assertEqual(environment, [("image", "environment.png")])
        self.assertEqual(pool, [("image", "pool.png")])
        self.assertEqual(signature, [("image", "signature.png")])
        self.assertEqual(sickness, [("image", "sickness.png")])
        plugin.player_meta_service.get_player_environment.assert_awaited_once_with(
            "1287101468", season="S9.5"
        )
        plugin.player_career_analysis_service.get_hero_pool_analysis.assert_awaited_once_with(
            "1287101468", AnalysisScope.season("19")
        )
        self.assertEqual(plugin.player_signature_service.get_player_signature.await_count, 2)
        self.assertEqual(
            plugin.player_signature_service.get_player_signature.await_args_list,
            [(("1287101468",), {"top_n": 5}), (("1287101468",), {"top_n": 5})],
        )

    async def test_signature_accepts_explicit_season_filter(self):
        plugin = plugin_with()
        result = [item async for item in plugin.my_signature(FakeEvent(), "S9.5", "")]
        self.assertEqual(result, [("image", "signature.png")])
        plugin.player_signature_service.get_player_signature.assert_awaited_with(
            "123", top_n=5, season="S9.5"
        )

    async def test_image_failure_falls_back_to_text(self):
        plugin = plugin_with(render_error=RuntimeError("render"))
        result = [item async for item in plugin.my_hero_pool(FakeEvent())]
        self.assertEqual(result[0][0], "text")
        self.assertIn("我的英雄池", result[0][1])

    async def test_hero_pool_uses_shared_analysis_instead_of_legacy_meta_service(self):
        plugin = plugin_with()
        pool = SimpleNamespace(
            uid="1287101468",
            player_name="玩家",
            scope=AnalysisScope.season("19"),
            total_matches=10,
            active_heroes=1,
            core_heroes=(),
            top1_share=100.0,
            top3_share=100.0,
            effective_pool_width=1.0,
            vanguard_share=0.0,
            duelist_share=100.0,
            strategist_share=0.0,
            weighted_performance=None,
            positive_usage_share=0.0,
            negative_usage_share=0.0,
            structure_tags=("单核专精",),
            meta_available=False,
            meta_stale=False,
        )
        shared = SimpleNamespace(
            get_hero_pool_analysis=AsyncMock(return_value=pool),
        )
        plugin.player_career_analysis_service = shared
        plugin.image_renderer.player_hero_pool_analysis = AsyncMock(return_value="shared-pool.png")

        result = [item async for item in plugin.my_hero_pool(FakeEvent(), "S9.5", "uid=1287101468")]

        self.assertEqual(result, [("image", "shared-pool.png")])
        shared.get_hero_pool_analysis.assert_awaited_once_with(
            "1287101468", AnalysisScope.season("19")
        )
        plugin.player_meta_service.get_player_hero_pool.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
