import unittest
from unittest.mock import AsyncMock

from rendering import MatchImageRenderer, RivalsImageRenderer
from rendering.cards import _PNG_OPTIONS, _STYLE
from rendering.components import metric_grid, page_shell
from rendering.formatters import escape_text
from rendering.pages import (
    build_hero_query_html,
    build_match_detail_html,
    build_player_stats_html,
    build_recent_matches_html,
)
from rendering.pages.hero import build_hero_query_html as hero_page
from rendering.pages.match_detail import build_match_detail_html as match_page
from rendering.pages.player import build_player_stats_html as player_page
from rendering.pages.recent import build_recent_matches_html as recent_page
from rendering.renderer import PNG_OPTIONS
from rendering.theme import STYLE


class TestRenderingArchitecture(unittest.TestCase):
    def test_public_rendering_exports_point_to_page_modules(self):
        self.assertIs(build_hero_query_html, hero_page)
        self.assertIs(build_match_detail_html, match_page)
        self.assertIs(build_player_stats_html, player_page)
        self.assertIs(build_recent_matches_html, recent_page)

    def test_legacy_renderer_name_and_cards_module_remain_compatible(self):
        self.assertIs(MatchImageRenderer, RivalsImageRenderer)
        self.assertEqual(_STYLE, STYLE)
        self.assertEqual(_PNG_OPTIONS, PNG_OPTIONS)

    def test_shared_components_keep_dynamic_text_escaped(self):
        html = page_shell(metric_grid((("<label>", "<value>{{danger}}</value>"), ("empty", None))))
        self.assertNotIn("<label>", html)
        self.assertNotIn("<value>", html)
        self.assertNotIn("{{danger}}", html)
        self.assertIn("<b>-</b>", html)
        self.assertNotIn("width:1040px", html)
        self.assertIn("width:100vw", html)
        self.assertEqual(escape_text("<unsafe>"), "&lt;unsafe&gt;")


class TestRenderingAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_semantic_renderer_alias_uses_existing_png_contract(self):
        html_render = AsyncMock(return_value="rendered.png")
        renderer = RivalsImageRenderer(html_render)

        self.assertEqual(await renderer.recent("123", "19", []), "rendered.png")
        call = html_render.await_args
        self.assertEqual(call.args[1], {})
        self.assertEqual(call.kwargs["options"], {
            "type": "png",
            "full_page": True,
            "animations": "disabled",
            "caret": "hide",
        })


if __name__ == "__main__":
    unittest.main()
