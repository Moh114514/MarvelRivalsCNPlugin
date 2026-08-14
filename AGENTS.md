# MR-bot Development Rules

## Scope

These rules apply to the entire repository.

## Source Layout

- The repository root is the AstrBot plugin root.
- `main.py`, `metadata.yaml`, `_conf_schema.json`, `requirements.txt`,
  `marvel_rivals_bot/`, `qq_official/`, and `rendering/` are the single shipped
  source tree. Do not create a second bundled core directory.
- AstrBot-only integration belongs in root `main.py`, metadata, and configuration
  files. Do not add AstrBot imports to `marvel_rivals_bot/`.

## API And Configuration

- Treat the NetEase mini-program API as an observed, unstable interface. Keep endpoint paths and request templates configurable.
- Preserve the original numeric season code in API requests. Convert it to a user-facing season name only when formatting output.
- User-facing commands and CLI options accept season names such as `S9`, `S9.5`, or `S9上半赛季`, never raw numeric season codes. Conversion to the numeric API code belongs in the service boundary.
- Keep `game_mode_id`, `match_map_id`, `play_mode_id`, and third-party season namespaces separate. Never merge them into a generic mapping.
- Add map IDs only when evidence is reliable. Unknown map IDs must retain their numeric ID and must not receive guessed names.
- Never commit `access_token`, cookies, authorization headers, proxy certificates, captures, raw responses, local databases, or `.env.capture`.
- Do not disable TLS verification or route production requests through mitmproxy by default.
- Maintain compatibility with existing configuration where practical, especially old request templates.

## User-Facing Behavior

- Bot output and user-safe errors are written in Simplified Chinese.
- Commands documented in `/help`, `/帮助`, and `README.md` must match the implemented AstrBot handlers.
- `/help` is an AstrBot built-in command. Do not register another `help` handler; maintain command docstrings so built-in help can describe this plugin.
- When adding or changing a command, update its help text, examples, argument descriptions, and tests together.
- Unknown hero IDs and rank levels must use explicit fallbacks instead of guessed names.
- Hero query commands accept mapped Chinese hero names, not numeric hero IDs. Convert names to IDs before calling the data source.

## Versioning And Packaging

- When shipped plugin behavior changes, update the release version in
  `metadata.yaml`, root `main.py`, and `pyproject.toml` together. The release
  validator in `tools/release.py` is the source of truth for consistency checks.
- Keep `_conf_schema.json`, `.env.example`, and runtime defaults synchronized.
- Build a release archive with `python tools/release.py --build
  dist/astrbot_plugin_marvel_rivals-v<version>.zip`; the archive is ignored by Git.

## Verification

- Run `python -m unittest discover -s tests -v` after every code change.
- Run `python -m py_compile` for modified runtime modules when syntax or imports changed.
- Run `git diff --check` before delivery.
- Run `python tools/release.py --check` for every release-related change.
- For changes to request bodies or response parsing, add MockTransport coverage. Use a live API query only when credentials are locally available, and never expose the token in output.
- Do not claim historical-season or endpoint support based only on mocks; verify once against the live interface when feasible.

## Change Discipline

- Keep changes scoped to the current request and preserve unrelated user modifications in the dirty worktree.
- Do not commit generated captures, debug responses, caches, or local environment files.
- Do not use destructive Git commands or overwrite user changes.

## Planned Visual System v1

The following is the approved planning boundary for the future Marvel Rivals visual-system work. It is a plan only; do not implement it unless a later task explicitly asks for a phase. The full local planning document is `docs/marvel-rivals-visual-system-v1.plan.md` and is intentionally ignored by Git.

### Scope And Output Contract

- Preserve the current HTML/CSS -> AstrBot `html_render()` -> PNG pipeline. Do not replace it with Pillow or another renderer.
- Keep the root directory as the only AstrBot plugin source tree. The planned rendering split is `rendering/renderer.py`, `theme.py`, `components.py`, `formatters.py`, and `pages/{player,recent,match_detail,hero}.py`; do not create a second core directory.
- Target image-first output: `/战绩`, `/查询`, `/英雄数据`, and `/对局详情` send one complete image without navigation buttons; `/最近对局` sends the image plus meaningful selection buttons for matches 1-10; `/卡片测试` remains a capability-test card.
- Image content must remain platform-neutral. Do not put QQ Official button instructions inside rendered images.
- Keep `rendering/__init__.py` stable through re-exports. Rename the implementation to `RivalsImageRenderer` only with a temporary `MatchImageRenderer` compatibility alias.
- Do not create duplicate UI ViewModels. Reuse existing business models and keep raw-match parsing changes separate from the visual refactor.

### Visual Rules

- Visual System v1.1 uses a restrained Marvel Rivals editorial direction: a quiet cold blue-gray field is the default (`#E1E5F1` family), purple carries the main text and structural emphasis (`#2F205B` primary, `#6842B4` accent), and warm yellow near `#FBDC2B` is reserved for edges, priority states, and small separators. Cyan is not a standard content color; muted red remains reserved for loss/danger cues.
- The current approved visual assets are `rendering/assets/part-news-bg_ac16ec22.png` and `rendering/assets/list-l_8a1441f6.png`, used only through `rendering/asset_loader.py` with a CSS fallback. Do not add additional background JPG/PNG, official hero art, map art, custom fonts, or assets without a separate licensing and packaging review.
- Runtime remote image caching is implemented in `rendering/assets.py` through `AssetManager`. Cache files belong under AstrBot `data/plugin_data/astrbot_plugin_marvel_rivals/assets/`, never in the source tree or release ZIP. Do not guess an unstable image endpoint; only pass through image URLs observed in confirmed API responses. Warmup is optional and must never block plugin startup or make CSS-only rendering unavailable.
- Centralize theme tokens and shared CSS in `rendering/theme.py`; pages must use theme variables instead of scattered hard-coded colors.
- Keep the center visually quiet. Concentrate yellow and geometric decoration at the top/bottom edges, corners, and local separators; never let large bands or diagonal planes cross the main content. Background geometry should use low-contrast, irregular pointed facets with a few focal convergence points and varied widths, not repeated parallel parallelograms. Large regions should have no radius, and decorative watermarks should remain invisible.
- The shared Header must make the subject primary: render `title_cn` as a dark nameplate with light text and a yellow edge/offset, while the English page type remains a weak eyebrow/title. Keep the season badge, but remove redundant labels such as `SUBJECT` and avoid an isolated `MR // DATA` block competing with the subject.
- Keep rank and score in a compact high-contrast header metadata group rather than treating them as gray subtitle text; rank should be slightly wider/larger than secondary metadata. Metrics form one integrated light information band with dividers, using clearly oversized values and a smaller K/D/A variant; hero and match rows stay light and calm instead of alternating dark/light cards. Only Top 1/Top 3 may receive stronger emphasis.
- Ordered two-column lists must fill top-to-bottom before moving to the next column: 01–05 in the first column, then 06–10 in the second. Apply this consistently to hero, recent-match, and any future numbered list views; reset to normal row flow when the layout becomes one column.
- Keep ordinary readable text at 15px or above on the rendered PNG, metric values at 25px or above, hero names at 20px or above, and player names at 28px or above where they are the page subject. Decorative English may be smaller only when it carries no data.
- Keep `width: 100vw`, `full_page=True`, and the existing responsive viewport strategy. Do not restore a fixed 1040px/1200px canvas.
- The first visual reference page is `/战绩`; establish the nameplate, compact rank metadata, integrated metric band, light hero list, typography, cold quiet background, pointed low-contrast facets, and edge geometry there before migrating other pages.

### Safety, Tests, And Non-goals

- Preserve HTML escaping and dynamic-text safety while moving formatters. Unknown hero/map/rank values and empty data must use explicit fallbacks.
- Test semantic structure and behavior, not pixel-level CSS strings or complete HTML snapshots. Continue covering text, buttons, XSS escaping, QQ payloads, image-only output, and `100vw`/PNG options; add theme/page-shell/numbering/fallback coverage as needed.
- Visual changes require manual screenshots with fixed player/recent/hero/match fixtures on both PC QQ and mobile QQ. Mocked `html_render` tests do not replace visual acceptance; the acceptance checklist must explicitly review name contrast, mobile text scale, quiet center space, edge-only decoration, and absence of dashboard-like filler.
- Do not change the API, capture mechanism, token, season mapping, hero-ID mapping, UID binding, database, command names, or recent-ten-match business logic as part of this visual work.
- Do not add Pillow, Playwright, or new runtime dependencies. Keep the approved PNG assets in the explicit release allowlist and keep the archive under the existing size budget.
- Asset downloads must use the existing `httpx` dependency, a bounded concurrency limit, recognizable image signature validation, conditional revalidation where available, and atomic replacement. Never forward `access_token`, cookies, or authorization headers to image CDNs by default.

### Delivery Order

1. PR1: split the rendering architecture without changing output behavior or visual appearance.
2. PR2: introduce the shared Marvel Rivals CSS/HTML theme and migrate `/战绩`, `/英雄数据`, `/最近对局`, then `/对局详情`; the theme must follow the restrained v1.1 editorial rules above.
3. PR3: add a semantic `QQOfficialCardSender.send_image()` API and clean up image-only card builders while retaining recent-match buttons.
4. The approved asset slice is now delivered with the asset loader, CSS fallback, release allowlist, packaging tests, and size budget checks; future asset additions still require a separate licensing review.

The current release target is `v0.13.3`; when shipped behavior changes again, synchronize `metadata.yaml`, `main.py`, and `pyproject.toml` and run the release checks.
