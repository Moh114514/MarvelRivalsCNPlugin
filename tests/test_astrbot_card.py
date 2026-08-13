import unittest

from astrbot_plugin_marvel_rivals.main import MarvelRivalsPlugin
from marvel_rivals_bot.models import PlayerProfile, PlayerStats


class FakeEvent:
    def plain_result(self, value):
        return ("text", value)

    def image_result(self, value):
        return ("image", value)


class FakeService:
    def __init__(self):
        self.stats_calls = 0
        self.text_calls = 0

    async def get_player_stats(self, uid, season):
        self.stats_calls += 1
        return PlayerStats(profile=PlayerProfile(uid=uid, name="Tester"), season="19")

    async def player_text(self, uid, season):
        self.text_calls += 1
        return f"text:{uid}:{season}"


async def collect(generator):
    return [item async for item in generator]


class TestAstrBotCard(unittest.IsolatedAsyncioTestCase):
    def plugin(self, *, enabled=True, fallback=True):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.service = FakeService()
        plugin.bindings = None
        plugin.card_enabled = enabled
        plugin.card_theme = "dark"
        plugin.card_fallback_text = fallback
        return plugin

    async def test_stats_card_renders_image(self):
        plugin = self.plugin()

        async def html_render(template, data, options):
            self.assertIn("{{ player.name|e }}", template)
            self.assertEqual(data["player"]["name"], "Tester")
            self.assertEqual(options["type"], "png")
            return "image-url"

        plugin.html_render = html_render
        results = await collect(plugin._stats_card_query(FakeEvent(), "1", "S9.5"))
        self.assertEqual(results, [("image", "image-url")])
        self.assertEqual(plugin.service.stats_calls, 1)

    async def test_stats_card_render_failure_uses_same_stats_for_text(self):
        plugin = self.plugin()

        async def html_render(*_args, **_kwargs):
            raise RuntimeError("renderer unavailable")

        plugin.html_render = html_render
        results = await collect(plugin._stats_card_query(FakeEvent(), "1", None))
        self.assertEqual(results[0][0], "text")
        self.assertIn("Tester", results[0][1])
        self.assertEqual(plugin.service.stats_calls, 1)
        self.assertEqual(plugin.service.text_calls, 0)

    async def test_disabled_card_and_query_alias_stay_text_only(self):
        plugin = self.plugin(enabled=False)
        results = await collect(plugin._stats_card_query(FakeEvent(), "1", None))
        self.assertEqual(results[0][0], "text")
        self.assertIn("Tester", results[0][1])

        query_results = await collect(plugin._query(FakeEvent(), "1", "S9.5"))
        self.assertEqual(query_results, [("text", "text:1:S9.5")])
        self.assertEqual(plugin.service.text_calls, 1)


if __name__ == "__main__":
    unittest.main()
