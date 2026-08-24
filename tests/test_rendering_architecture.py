import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from rendering import MatchImageRenderer, RivalsImageRenderer
from rendering.cards import _PNG_OPTIONS, _STYLE
from rendering.components import metric_grid, page_shell
from rendering.formatters import escape_text
from rendering.pages import (
    build_help_html,
    build_hero_query_html,
    build_match_detail_html,
    build_player_hero_pool_analysis_html,
    build_player_stats_html,
    build_recent_matches_html,
)
from rendering.pages.hero import build_hero_query_html as hero_page
from rendering.pages.help import build_help_html as help_page
from rendering.pages.match_detail import build_match_detail_html as match_page
from rendering.pages.player import build_player_stats_html as player_page
from rendering.pages.recent import build_recent_matches_html as recent_page
from rendering.pages.player_hero_pool_analysis import (
    build_player_hero_pool_analysis_html as player_hero_pool_analysis_page,
)
from rendering.renderer import PNG_OPTIONS
from rendering.theme import STYLE


class TestRenderingArchitecture(unittest.TestCase):
    def test_public_rendering_exports_point_to_page_modules(self):
        self.assertIs(build_help_html, help_page)
        self.assertIs(build_hero_query_html, hero_page)
        self.assertIs(build_match_detail_html, match_page)
        self.assertIs(build_player_hero_pool_analysis_html, player_hero_pool_analysis_page)
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
        self.assertIn('class="mr-metric__value">-</b>', html)
        self.assertIn('class="mr-page"', html)
        self.assertIn('class="mr-page__background"', html)
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

        self.assertEqual(await renderer.help("/帮助\n显示完整指令帮助"), "rendered.png")
        self.assertIn("COMMAND GUIDE", html_render.await_args.args[0])

    async def test_render_retries_once_and_preserves_final_failure(self):
        html_render = AsyncMock(side_effect=[RuntimeError("temporary"), "rendered.png"])
        renderer = RivalsImageRenderer(html_render, max_retries=1)

        self.assertEqual(await renderer.help("help"), "rendered.png")
        self.assertEqual(html_render.await_count, 2)

        final_error = RuntimeError("permanent")
        failing_render = AsyncMock(side_effect=final_error)
        renderer = RivalsImageRenderer(failing_render, max_retries=0)
        with self.assertRaises(RuntimeError) as raised:
            await renderer.help("help")
        self.assertIs(raised.exception, final_error)

    async def test_render_queue_timeout_is_bounded(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        async def html_render(*args, **kwargs):
            entered.set()
            await release.wait()
            return "rendered.png"

        renderer = RivalsImageRenderer(
            html_render,
            max_concurrent_renders=1,
            max_retries=0,
            queue_timeout_seconds=0.01,
        )
        first = asyncio.create_task(renderer.help("first"))
        await asyncio.wait_for(entered.wait(), timeout=1)
        with self.assertRaises(asyncio.TimeoutError):
            await renderer.help("second")
        release.set()
        self.assertEqual(await first, "rendered.png")

    async def test_render_semaphore_limits_parallel_pages(self):
        active = 0
        maximum = 0
        entered = 0
        started = asyncio.Event()
        release = asyncio.Event()

        async def html_render(*args, **kwargs):
            nonlocal active, maximum, entered
            active += 1
            entered += 1
            maximum = max(maximum, active)
            if entered == 2:
                started.set()
            await release.wait()
            active -= 1
            return "rendered.png"

        renderer = RivalsImageRenderer(html_render, max_concurrent_renders=2, max_retries=0)
        tasks = [asyncio.create_task(renderer.help(f"help-{index}")) for index in range(4)]
        await asyncio.wait_for(started.wait(), timeout=1)
        self.assertEqual(maximum, 2)
        self.assertEqual(entered, 2)
        release.set()
        self.assertEqual(await asyncio.gather(*tasks), ["rendered.png"] * 4)

    async def test_detail_render_logs_queue_and_execution_timings(self):
        logger = Mock()
        renderer = RivalsImageRenderer(
            AsyncMock(return_value="rendered.png"),
            max_retries=0,
            logger=logger,
        )

        self.assertEqual(
            await renderer.detail({"data": {"matches": [{"matchPlayers": []}]}}),
            "rendered.png",
        )
        messages = " ".join(call.args[0] for call in logger.info.call_args_list)
        self.assertIn("render_type=detail", messages)
        self.assertIn("queue_ms=", messages)
        self.assertIn("execution_ms=", messages)


if __name__ == "__main__":
    unittest.main()
