# MR-bot Development Rules

## Scope

These rules apply to the entire repository.

## Source Layout

- `marvel_rivals_bot/` is the development copy of the core package.
- `astrbot_plugin_marvel_rivals/marvel_rivals_bot/` is the bundled copy shipped with the standalone AstrBot plugin.
- Any change to shared core code must be applied to both locations in the same task.
- Shared files must remain byte-for-byte identical. The synchronization test in `tests/test_astrbot_package.py` must pass.
- AstrBot-only integration belongs in `astrbot_plugin_marvel_rivals/main.py`, metadata, and configuration files. Do not add AstrBot imports to the shared core package.

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

- When shipped plugin behavior changes, update the version in both `astrbot_plugin_marvel_rivals/main.py` and `metadata.yaml`.
- Keep `_conf_schema.json`, `.env.example`, and runtime defaults synchronized.
- After plugin changes, rebuild `astrbot_plugin_marvel_rivals.zip`. The archive remains ignored by Git.

## Verification

- Run `python -m unittest discover -s tests -v` after every code change.
- Run `python -m py_compile` for modified runtime modules when syntax or imports changed.
- Run `git diff --check` before delivery.
- For changes to request bodies or response parsing, add MockTransport coverage. Use a live API query only when credentials are locally available, and never expose the token in output.
- Do not claim historical-season or endpoint support based only on mocks; verify once against the live interface when feasible.

## Change Discipline

- Keep changes scoped to the current request and preserve unrelated user modifications in the dirty worktree.
- Do not commit generated captures, debug responses, caches, or local environment files.
- Do not use destructive Git commands or overwrite user changes.
